# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
任务调度器模块。

提供任务调度、执行和资源管理功能。
"""

import time
import asyncio
import logging
import threading
from typing import Dict, Any, List, Optional, Union, Tuple

from ..exceptions import TaskflowError
from .resource import ResourceManager
from .pools.llm_pool import LLMResourcePool
from .pools.database_pool import DatabaseResourcePool
from .pools.worker_pool import WorkerResourcePool
from .pools.api_pool import APIResourcePool

# 获取logger
logger = logging.getLogger(__name__)


class SchedulerError(TaskflowError):
    """调度器相关异常基类"""
    pass


class TaskScheduler:
    """任务调度器核心类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化任务调度器
        
        Args:
            config: 调度器配置字典
        """
        self.config = config or {}
        self.running = False
        self.scheduler_thread = None
        self.resource_manager = None
        self.initialization_complete = False
        self.lock = asyncio.Lock()
        
        # 初始化资源管理器
        self._init_resource_manager()
        
        logger.info("任务调度器初始化完成")
    
    def _init_resource_manager(self):
        """初始化资源管理器"""
        # 创建资源配置
        resource_config = self.config.get("resources", {})
        
        # 创建扩展的ResourceManager类，内置所有资源池
        class TaskflowResourceManager(ResourceManager):
            """任务流资源管理器，内置所有资源池"""
            
            async def _initialize_resource_pools(self):
                """初始化各类资源池"""
                # LLM资源池
                llm_config = self.config.get("llm", {})
                self.resource_pools["llm"] = LLMResourcePool(
                    max_concurrent=llm_config.get("max_concurrent", 5),
                    rate_limit=llm_config.get("rate_limit", 10),
                    time_window=llm_config.get("time_window", 60),
                    timeout=llm_config.get("timeout", 30)
                )
                
                # 数据库资源池
                db_config = self.config.get("database", {})
                self.resource_pools["database"] = DatabaseResourcePool(
                    max_connections=db_config.get("max_connections", 20),
                    idle_timeout=db_config.get("idle_timeout", 300),
                    max_age=db_config.get("max_age", 3600),
                    acquire_timeout=db_config.get("acquire_timeout", 10)
                )
                
                # 工作线程池
                worker_config = self.config.get("worker", {})
                self.resource_pools["worker"] = WorkerResourcePool(
                    max_workers=worker_config.get("max_workers", 10),
                    task_timeout=worker_config.get("task_timeout", 300)
                )
                
                # 外部API资源池
                api_config = self.config.get("api", {})
                self.resource_pools["api"] = APIResourcePool(
                    rate_limits=api_config.get("rate_limits", {}),
                    default_timeout=api_config.get("default_timeout", 30)
                )
                
                logger.info("资源池初始化完成")
        
        # 创建资源管理器实例
        self.resource_manager = TaskflowResourceManager(resource_config)
    
    async def initialize(self):
        """异步初始化"""
        if self.initialization_complete:
            return
            
        async with self.lock:
            if self.initialization_complete:
                return
                
            # 初始化资源管理器
            await self.resource_manager.initialize()
            
            # 标记初始化完成
            self.initialization_complete = True
            logger.info("任务调度器异步初始化完成")
            
    def start(self):
        """启动调度器"""
        if self.running:
            return
            
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        logger.info("任务调度器已启动")
        
    def stop(self):
        """停止调度器"""
        if not self.running:
            return
            
        logger.info("正在停止任务调度器...")
        self.running = False
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=10)
            if self.scheduler_thread.is_alive():
                logger.warning("调度器线程停止超时")
            else:
                logger.info("调度器线程已停止")
                
        # 异步关闭资源池（在主事件循环中执行）
        asyncio.create_task(self._shutdown_resources())
        
    async def _shutdown_resources(self):
        """关闭所有资源池"""
        logger.info("正在关闭资源池...")
        
        # 获取所有资源池
        resource_status = self.resource_manager.get_resource_status()
        
        # 关闭数据库连接池
        if "database" in self.resource_manager.resource_pools:
            db_pool = self.resource_manager.resource_pools["database"]
            await db_pool.shutdown()
            
        # 关闭工作线程池
        if "worker" in self.resource_manager.resource_pools:
            worker_pool = self.resource_manager.resource_pools["worker"]
            await worker_pool.shutdown(wait=True)
            
        logger.info("资源池已关闭")
            
    def _scheduler_loop(self):
        """调度器主循环"""
        try:
            # 确保资源管理器已初始化
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 异步初始化
            loop.run_until_complete(self.initialize())
            
            # 主循环
            while self.running:
                try:
                    # 调度任务
                    loop.run_until_complete(self._schedule_tasks())
                    
                    # 检查任务状态
                    loop.run_until_complete(self._check_task_status())
                    
                except Exception as e:
                    logger.error(f"调度器循环出错: {str(e)}", exc_info=True)
                    
                # 等待下一个检查周期
                time.sleep(self.config.get("check_interval", 30))
                
        except Exception as e:
            logger.error(f"调度器主循环异常: {str(e)}", exc_info=True)
        finally:
            # 关闭事件循环
            loop.close()
            
    async def _schedule_tasks(self):
        """调度待执行任务"""
        # 实际项目中，这里会从数据库获取待执行任务并调度
        # 示例实现
        logger.debug("检查待调度任务")
        
        # TODO: 从数据库获取待执行任务
        pending_tasks = []  # 示例，实际项目中从数据库获取
        
        for task in pending_tasks:
            try:
                # 分配资源
                await self._allocate_resources(task)
                
                # 更新任务状态为运行中
                # await self._update_task_status(task["id"], "RUNNING")
                
                # 启动任务执行
                # await self._execute_task(task)
                
            except Exception as e:
                logger.error(f"调度任务 {task.get('id')} 失败: {str(e)}")
                # 更新任务状态为失败
                # await self._update_task_status(task["id"], "FAILED", error=str(e))
                
    async def _check_task_status(self):
        """检查任务执行状态"""
        # 实际项目中，这里会检查正在执行的任务状态
        # 示例实现
        logger.debug("检查任务执行状态")
        
        # TODO: 从数据库获取运行中的任务
        running_tasks = []  # 示例，实际项目中从数据库获取
        
        for task in running_tasks:
            try:
                # 检查任务状态
                # status = await self._get_task_execution_status(task["id"])
                
                # 根据状态更新数据库
                # if status["completed"]:
                #     if status["success"]:
                #         await self._update_task_status(task["id"], "COMPLETED", result=status["result"])
                #     else:
                #         await self._update_task_status(task["id"], "FAILED", error=status["error"])
                pass
                
            except Exception as e:
                logger.error(f"检查任务 {task.get('id')} 状态失败: {str(e)}")
                
    async def _allocate_resources(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        为任务分配所需资源
        
        Args:
            task: 任务信息字典
            
        Returns:
            资源分配结果
        """
        task_priority = task.get("priority", 50)
        required_resources = task.get("required_resources", {})
        resource_handles = {}
        
        try:
            # 分配LLM资源（如果需要）
            if "llm" in required_resources:
                llm_resource = await self.resource_manager.acquire_resource(
                    "llm",
                    priority=task_priority,
                    timeout=required_resources.get("llm", {}).get("timeout", 30)
                )
                resource_handles["llm"] = llm_resource
                
            # 分配数据库资源（如果需要）
            if "database" in required_resources:
                db_resource = await self.resource_manager.acquire_resource(
                    "database",
                    priority=task_priority,
                    timeout=required_resources.get("database", {}).get("timeout", 10)
                )
                resource_handles["database"] = db_resource
                
            # 分配工作线程资源（如果需要）
            if "worker" in required_resources:
                worker_resource = await self.resource_manager.acquire_resource(
                    "worker",
                    priority=task_priority,
                    timeout=required_resources.get("worker", {}).get("timeout", 10)
                )
                resource_handles["worker"] = worker_resource
                
            return {
                "success": True,
                "task_id": task.get("id"),
                "resource_handles": resource_handles
            }
            
        except Exception as e:
            # 释放已分配的资源
            for resource_type, handle in resource_handles.items():
                try:
                    await self.resource_manager.release_resource(resource_type, handle)
                except Exception as release_error:
                    logger.error(f"释放资源 {resource_type} 失败: {str(release_error)}")
            
            return {
                "success": False,
                "task_id": task.get("id"),
                "error": str(e)
            }
            
    async def execute_task_with_resources(self, task_func, task_args=None, task_kwargs=None, 
                                       priority: int = 50, 
                                       required_resources: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        使用指定资源执行任务函数
        
        Args:
            task_func: 任务函数
            task_args: 任务函数位置参数
            task_kwargs: 任务函数关键字参数
            priority: 任务优先级
            required_resources: 所需资源配置
            
        Returns:
            任务执行结果
        """
        # 确保初始化完成
        await self.initialize()
        
        task_args = task_args or ()
        task_kwargs = task_kwargs or {}
        required_resources = required_resources or {"worker": {}}
        resource_handles = {}
        
        try:
            # 分配资源
            for resource_type in required_resources:
                resource_config = required_resources[resource_type]
                timeout = resource_config.get("timeout", 30)
                
                resource_handle = await self.resource_manager.acquire_resource(
                    resource_type,
                    priority=priority,
                    timeout=timeout
                )
                resource_handles[resource_type] = resource_handle
            
            # 提交任务到工作线程池执行
            if "worker" in self.resource_manager.resource_pools:
                worker_pool = self.resource_manager.resource_pools["worker"]
                
                # 提交任务
                task_id = await worker_pool.submit_task(
                    task_func, 
                    task_args, 
                    task_kwargs,
                    priority=priority
                )
                
                # 等待任务完成并获取结果
                result = await worker_pool.get_task_result(
                    task_id,
                    wait=True,
                    timeout=required_resources.get("worker", {}).get("timeout", 300)
                )
                
                return result
            else:
                # 如果没有工作线程池，直接执行任务
                try:
                    result = await task_func(*task_args, **task_kwargs)
                    return {
                        "success": True,
                        "result": result,
                        "task_id": "direct-execution"
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "task_id": "direct-execution"
                    }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
            
        finally:
            # 释放资源
            for resource_type, handle in resource_handles.items():
                try:
                    await self.resource_manager.release_resource(resource_type, handle)
                except Exception as release_error:
                    logger.error(f"释放资源 {resource_type} 失败: {str(release_error)}")
                    
    def get_resource_status(self) -> Dict[str, Any]:
        """
        获取资源状态
        
        Returns:
            资源状态字典
        """
        if not self.initialization_complete:
            return {"status": "未初始化"}
            
        return self.resource_manager.get_resource_status()
        
    async def get_scheduler_status(self) -> Dict[str, Any]:
        """
        获取调度器状态
        
        Returns:
            调度器状态字典
        """
        # 确保初始化完成
        await self.initialize()
        
        return {
            "running": self.running,
            "resources": self.get_resource_status(),
            "config": self.config
        } 