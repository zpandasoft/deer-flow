# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
工作线程池模块。

提供工作线程的资源管理，包括线程创建、分配和监控。
"""

import time
import uuid
import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, List, Callable, Tuple

from ..resource import ResourcePool, ResourceUnavailableError, ResourceTimeoutError

# 获取logger
logger = logging.getLogger(__name__)


class WorkerTask:
    """工作任务封装"""
    
    def __init__(self, task_id: str, func: Callable, args: Tuple, kwargs: Dict):
        self.task_id = task_id
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.created_at = time.time()
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.error = None
        self.is_completed = False
        self.is_error = False
        
    def __str__(self):
        return f"WorkerTask({self.task_id}, completed={self.is_completed})"
        
    def mark_started(self):
        """标记任务开始"""
        self.started_at = time.time()
        
    def mark_completed(self, result):
        """标记任务完成"""
        self.completed_at = time.time()
        self.result = result
        self.is_completed = True
        
    def mark_error(self, error):
        """标记任务失败"""
        self.completed_at = time.time()
        self.error = error
        self.is_completed = True
        self.is_error = True
        
    def get_execution_time(self) -> Optional[float]:
        """获取执行时间（秒）"""
        if self.started_at is None:
            return None
            
        end_time = self.completed_at or time.time()
        return end_time - self.started_at


class WorkerResourcePool(ResourcePool):
    """工作线程资源池实现"""
    
    def __init__(self, max_workers: int = 10, task_timeout: int = 300):
        """
        初始化工作线程池
        
        Args:
            max_workers: 最大工作线程数
            task_timeout: 任务超时时间（秒）
        """
        self.max_workers = max_workers
        self.task_timeout = task_timeout
        
        # 创建线程池执行器
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.semaphore = asyncio.Semaphore(max_workers)
        self.tasks = {}  # 任务字典
        self.task_lock = asyncio.Lock()
        self.monitoring_task = None
        
        self.usage_stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "timeout_tasks": 0,
            "peak_concurrent_tasks": 0,
            "avg_execution_time": 0,
            "total_execution_time": 0,
        }
        
        logger.info(f"工作线程池初始化: 最大工作线程={max_workers}, "
                   f"任务超时={task_timeout}秒")
        
    async def start_monitoring(self):
        """启动任务监控"""
        if self.monitoring_task is None or self.monitoring_task.done():
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            logger.debug("启动工作线程任务监控")
            
    async def _monitoring_loop(self):
        """监控任务执行情况"""
        try:
            while True:
                await asyncio.sleep(min(self.task_timeout // 5, 30))  # 最多每30秒检查一次
                await self._check_timeout_tasks()
        except asyncio.CancelledError:
            logger.debug("工作线程任务监控已取消")
        except Exception as e:
            logger.error(f"工作线程任务监控出错: {str(e)}")
            
    async def _check_timeout_tasks(self):
        """检查超时任务"""
        now = time.time()
        timeout_tasks = []
        
        async with self.task_lock:
            for task_id, task in list(self.tasks.items()):
                # 跳过已完成的任务
                if task.is_completed:
                    continue
                
                # 检查是否已开始但超时
                if task.started_at is not None and now - task.started_at > self.task_timeout:
                    timeout_tasks.append(task_id)
                    logger.warning(f"任务执行超时: {task}")
                    continue
                    
                # 检查是否在队列中等待太久
                if task.started_at is None and now - task.created_at > self.task_timeout * 2:
                    timeout_tasks.append(task_id)
                    logger.warning(f"任务等待超时: {task}")
                    continue
        
        # 标记超时任务
        for task_id in timeout_tasks:
            await self._mark_task_timeout(task_id)
            
    async def _mark_task_timeout(self, task_id: str):
        """标记任务超时"""
        async with self.task_lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.mark_error("Task execution timeout")
                self.usage_stats["timeout_tasks"] += 1
                logger.warning(f"标记任务超时: {task}")
                
    def _task_wrapper(self, task_id: str, func: Callable, args: Tuple, kwargs: Dict) -> Any:
        """
        任务包装函数，用于在线程中执行任务
        
        Args:
            task_id: 任务ID
            func: 要执行的函数
            args: 位置参数
            kwargs: 关键字参数
            
        Returns:
            函数执行结果
        """
        try:
            # 获取当前线程信息
            thread = threading.current_thread()
            logger.debug(f"线程 {thread.name} 开始执行任务 {task_id}")
            
            # 标记任务开始
            with asyncio.run_coroutine_threadsafe(self.task_lock.acquire(), asyncio.get_event_loop()) as _:
                if task_id in self.tasks:
                    self.tasks[task_id].mark_started()
            
            # 执行任务
            result = func(*args, **kwargs)
            
            # 标记任务完成
            with asyncio.run_coroutine_threadsafe(self.task_lock.acquire(), asyncio.get_event_loop()) as _:
                if task_id in self.tasks:
                    self.tasks[task_id].mark_completed(result)
                    self.usage_stats["completed_tasks"] += 1
                    
                    # 更新统计信息
                    execution_time = self.tasks[task_id].get_execution_time()
                    if execution_time is not None:
                        self.usage_stats["total_execution_time"] += execution_time
                        if self.usage_stats["completed_tasks"] > 0:
                            self.usage_stats["avg_execution_time"] = (
                                self.usage_stats["total_execution_time"] / 
                                self.usage_stats["completed_tasks"]
                            )
            
            logger.debug(f"线程 {thread.name} 完成任务 {task_id}")
            return result
            
        except Exception as e:
            logger.error(f"线程 {threading.current_thread().name} 执行任务 {task_id} 出错: {str(e)}")
            
            # 标记任务失败
            with asyncio.run_coroutine_threadsafe(self.task_lock.acquire(), asyncio.get_event_loop()) as _:
                if task_id in self.tasks:
                    self.tasks[task_id].mark_error(str(e))
                    self.usage_stats["failed_tasks"] += 1
            
            # 重新抛出异常
            raise
        finally:
            # 释放信号量
            self.semaphore.release()
        
    async def submit_task(self, func: Callable, args: Tuple = (), 
                          kwargs: Dict = None, priority: int = 0) -> str:
        """
        提交任务到线程池
        
        Args:
            func: 要执行的函数
            args: 位置参数
            kwargs: 关键字参数
            priority: 优先级（目前未使用）
            
        Returns:
            任务ID
        """
        kwargs = kwargs or {}
        
        # 获取一个工作线程资源
        await self.acquire_resource(priority=priority)
        
        # 生成任务ID
        task_id = f"worker-{uuid.uuid4()}"
        
        # 创建任务对象
        task = WorkerTask(task_id, func, args, kwargs)
        
        # 记录任务
        async with self.task_lock:
            self.tasks[task_id] = task
            self.usage_stats["total_tasks"] += 1
            
            # 更新峰值并发任务数
            current_tasks = sum(1 for t in self.tasks.values() if not t.is_completed)
            if current_tasks > self.usage_stats["peak_concurrent_tasks"]:
                self.usage_stats["peak_concurrent_tasks"] = current_tasks
        
        # 提交到线程池
        self.executor.submit(self._task_wrapper, task_id, func, args, kwargs)
        logger.debug(f"提交任务到线程池: {task}")
        
        # 启动监控（如果未启动）
        await self.start_monitoring()
        
        return task_id
        
    async def acquire(self, amount: int = 1, priority: int = 0, 
                     timeout: Optional[float] = None) -> Any:
        """
        获取工作线程资源
        
        Args:
            amount: 请求资源数量（通常为1）
            priority: 优先级（0-100）
            timeout: 超时时间（秒）
            
        Returns:
            True表示成功获取资源
            
        Raises:
            ResourceUnavailableError: 无法获取资源
            ResourceTimeoutError: 获取资源超时
        """
        if amount != 1:
            logger.warning(f"工作线程池不支持批量获取，忽略amount={amount}，只获取1个线程")
        
        try:
            # 尝试获取信号量
            acquired = await asyncio.wait_for(
                self.semaphore.acquire(),
                timeout=timeout
            )
            
            if not acquired:
                raise ResourceUnavailableError("无法获取工作线程资源")
                
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"获取工作线程资源超时 (timeout={timeout}秒)")
            raise ResourceTimeoutError(f"获取工作线程资源超时 (timeout={timeout}秒)")
        
    async def release(self, resource_handle: Any) -> None:
        """
        释放工作线程资源
        
        Args:
            resource_handle: 资源句柄（由于此方法通常在内部使用，此参数被忽略）
        """
        # 由于工作线程资源在任务完成时自动释放，此方法通常不会直接调用
        # 如果外部调用，则释放一个信号量
        self.semaphore.release()
        logger.debug("释放工作线程资源")
        
    def get_status(self) -> Dict[str, Any]:
        """
        获取资源池状态
        
        Returns:
            资源状态字典
        """
        # 计算活跃任务数
        active_tasks = sum(1 for task in self.tasks.values() if not task.is_completed)
        
        return {
            "type": "worker",
            "max_workers": self.max_workers,
            "available_workers": self.semaphore._value,
            "active_tasks": active_tasks,
            "total_tasks": len(self.tasks),
            "usage_stats": self.usage_stats
        }
        
    async def get_task_result(self, task_id: str, 
                             wait: bool = False, 
                             timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            wait: 是否等待任务完成
            timeout: 等待超时时间（秒）
            
        Returns:
            任务结果字典
        """
        # 检查任务是否存在
        async with self.task_lock:
            if task_id not in self.tasks:
                return {
                    "success": False,
                    "error": "任务不存在",
                    "task_id": task_id
                }
                
            task = self.tasks[task_id]
            
            # 如果任务已完成，直接返回结果
            if task.is_completed:
                if task.is_error:
                    return {
                        "success": False,
                        "error": task.error,
                        "task_id": task_id,
                        "execution_time": task.get_execution_time()
                    }
                else:
                    return {
                        "success": True,
                        "result": task.result,
                        "task_id": task_id,
                        "execution_time": task.get_execution_time()
                    }
        
        # 如果不等待，返回进行中状态
        if not wait:
            return {
                "success": None,  # 表示进行中
                "task_id": task_id,
                "execution_time": task.get_execution_time(),
                "status": "running" if task.started_at else "queued"
            }
            
        # 等待任务完成
        start_time = time.time()
        while True:
            # 检查超时
            if timeout is not None and time.time() - start_time > timeout:
                return {
                    "success": None,
                    "task_id": task_id,
                    "error": "等待任务结果超时",
                    "execution_time": task.get_execution_time(),
                    "status": "running" if task.started_at else "queued"
                }
                
            # 检查任务状态
            async with self.task_lock:
                if task_id in self.tasks:
                    task = self.tasks[task_id]
                    if task.is_completed:
                        if task.is_error:
                            return {
                                "success": False,
                                "error": task.error,
                                "task_id": task_id,
                                "execution_time": task.get_execution_time()
                            }
                        else:
                            return {
                                "success": True,
                                "result": task.result,
                                "task_id": task_id,
                                "execution_time": task.get_execution_time()
                            }
                else:
                    return {
                        "success": False,
                        "error": "任务不存在",
                        "task_id": task_id
                    }
                    
            # 短暂等待后重试
            await asyncio.sleep(0.1)
        
    async def shutdown(self, wait: bool = True):
        """
        关闭线程池
        
        Args:
            wait: 是否等待所有任务完成
        """
        logger.info(f"关闭工作线程池，wait={wait}")
        
        # 取消监控任务
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
                
        # 关闭线程池
        self.executor.shutdown(wait=wait)
        
        # 如果不等待，标记所有未完成的任务为错误
        if not wait:
            async with self.task_lock:
                for task_id, task in self.tasks.items():
                    if not task.is_completed:
                        task.mark_error("Worker pool shutdown")
                        self.usage_stats["failed_tasks"] += 1 