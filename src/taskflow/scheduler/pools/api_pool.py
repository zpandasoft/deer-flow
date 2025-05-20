# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
外部API资源池模块。

提供外部API调用的资源管理，包括速率限制、并发控制和调用监控。
"""

import time
import asyncio
import logging
from collections import deque, defaultdict
from typing import Dict, Any, Optional, List, Set, Union

from ..resource import ResourcePool, ResourceUnavailableError, ResourceTimeoutError

# 获取logger
logger = logging.getLogger(__name__)


class APIRateLimiter:
    """API速率限制器"""
    
    def __init__(self, name: str, calls: int, period: int):
        """
        初始化速率限制器
        
        Args:
            name: API名称
            calls: 在period时间内允许的最大调用次数
            period: 时间窗口（秒）
        """
        self.name = name
        self.max_calls = calls
        self.period = period
        self.call_times = deque(maxlen=calls)
        self.priority_thresholds = {
            "high": 80,    # 高优先级阈值
            "medium": 50,  # 中优先级阈值
            "low": 0       # 低优先级阈值
        }
        
    async def acquire(self, priority: int = 0) -> bool:
        """
        尝试获取调用令牌
        
        Args:
            priority: 请求优先级（0-100）
            
        Returns:
            是否允许调用
        """
        now = time.time()
        
        # 如果未达到限制，直接允许
        if len(self.call_times) < self.max_calls:
            self.call_times.append(now)
            return True
            
        # 检查最早的调用是否已经过期
        oldest = self.call_times[0]
        if now - oldest > self.period:
            self.call_times.popleft()  # 移除最早的调用
            self.call_times.append(now)
            return True
            
        # 对高优先级请求特殊处理
        if priority >= self.priority_thresholds["high"]:
            logger.info(f"高优先级请求({priority})突破了API '{self.name}' 速率限制")
            self.call_times.popleft()  # 移除最早的调用
            self.call_times.append(now)
            return True
            
        # 计算需要等待的时间
        wait_time = self.period - (now - oldest)
        
        # 对中优先级请求稍等一会再重试
        if priority >= self.priority_thresholds["medium"]:
            logger.debug(f"中优先级请求({priority})等待API '{self.name}' 速率限制: {wait_time:.2f}秒")
            await asyncio.sleep(min(wait_time, 1.0))  # 最多等待1秒
            return await self.acquire(priority)  # 递归重试
            
        # 低优先级请求需要等待完整时间或拒绝
        if wait_time < 5.0:  # 如果等待时间不太长
            logger.debug(f"低优先级请求({priority})等待API '{self.name}' 速率限制: {wait_time:.2f}秒")
            await asyncio.sleep(wait_time)
            return await self.acquire(priority)  # 递归重试
        else:
            logger.debug(f"低优先级请求({priority})被API '{self.name}' 速率限制拒绝，需等待: {wait_time:.2f}秒")
            return False  # 拒绝请求
        
    def reset(self):
        """重置速率限制器"""
        self.call_times.clear()


class APIResourcePool(ResourcePool):
    """外部API资源池实现"""
    
    def __init__(self, rate_limits: Dict[str, Dict[str, Any]] = None, 
                default_timeout: float = 30):
        """
        初始化API资源池
        
        Args:
            rate_limits: API速率限制配置，格式为
                         {'api_name': {'calls': 100, 'period': 60}}
            default_timeout: 默认超时时间（秒）
        """
        self.default_timeout = default_timeout
        self.limiters = {}  # API速率限制器字典
        self.locks = {}     # API锁字典
        self.semaphores = {}  # API并发限制信号量
        
        # 使用状态
        self.usage_stats = defaultdict(lambda: {
            "total_calls": 0,
            "failed_calls": 0,
            "timeouts": 0,
            "avg_response_time": 0.0,
            "total_response_time": 0.0,
            "last_call_time": None
        })
        
        # 初始化速率限制器
        self._initialize_rate_limiters(rate_limits or {})
        
        logger.info(f"API资源池初始化完成，配置了 {len(self.limiters)} 个API限制器")
        
    def _initialize_rate_limiters(self, rate_limits: Dict[str, Dict[str, Any]]):
        """初始化速率限制器"""
        # 为每个API创建速率限制器
        for api_name, config in rate_limits.items():
            calls = config.get("calls", 100)
            period = config.get("period", 60)
            max_concurrent = config.get("max_concurrent", 10)
            
            self.limiters[api_name] = APIRateLimiter(api_name, calls, period)
            self.locks[api_name] = asyncio.Lock()
            self.semaphores[api_name] = asyncio.Semaphore(max_concurrent)
            
            logger.debug(f"创建API '{api_name}' 限制器: {calls}次/{period}秒, "
                        f"最大并发: {max_concurrent}")
        
    def _get_limiter(self, api_name: str) -> APIRateLimiter:
        """获取或创建API限制器"""
        if api_name not in self.limiters:
            # 使用默认配置
            logger.warning(f"API '{api_name}' 未配置速率限制，使用默认配置")
            self.limiters[api_name] = APIRateLimiter(api_name, 60, 60)  # 默认1分钟60次
            self.locks[api_name] = asyncio.Lock()
            self.semaphores[api_name] = asyncio.Semaphore(5)  # 默认最多5个并发
            
        return self.limiters[api_name]
        
    def _get_semaphore(self, api_name: str) -> asyncio.Semaphore:
        """获取API并发信号量"""
        if api_name not in self.semaphores:
            self._get_limiter(api_name)  # 确保创建相关资源
            
        return self.semaphores[api_name]
        
    async def acquire(self, amount: int = 1, priority: int = 0, 
                     timeout: Optional[float] = None) -> Any:
        """
        获取API调用资源
        
        此方法通常不直接使用，而是使用api_call方法
        
        Args:
            amount: 请求数量（对API调用通常为1）
            priority: 优先级（0-100）
            timeout: 超时时间（秒）
            
        Returns:
            获取资源的标识符
            
        Raises:
            ResourceUnavailableError: 无法获取资源
            ResourceTimeoutError: 获取资源超时
        """
        # 这个方法主要用于兼容ResourcePool接口，实际使用api_call方法
        return "api_resource"
        
    async def release(self, resource_handle: Any) -> None:
        """
        释放API调用资源
        
        此方法通常不直接使用，而是由api_call自动处理
        
        Args:
            resource_handle: 资源句柄
        """
        # API调用完成后自动释放，无需额外操作
        pass
        
    def get_status(self) -> Dict[str, Any]:
        """
        获取资源池状态
        
        Returns:
            资源状态字典
        """
        api_statuses = {}
        
        for api_name, limiter in self.limiters.items():
            api_statuses[api_name] = {
                "max_calls": limiter.max_calls,
                "period": limiter.period,
                "current_usage": len(limiter.call_times),
                "usage_stats": dict(self.usage_stats[api_name]),
                "max_concurrent": self.semaphores[api_name]._value
            }
            
        return {
            "type": "api",
            "apis": api_statuses
        }
        
    async def api_call(self, api_name: str, call_func, *args, 
                      priority: int = 0, timeout: Optional[float] = None, 
                      **kwargs) -> Any:
        """
        执行API调用，自动处理速率限制和资源管理
        
        Args:
            api_name: API名称
            call_func: 调用函数
            *args: 调用函数的位置参数
            priority: 优先级（0-100）
            timeout: 超时时间（秒）
            **kwargs: 调用函数的关键字参数
            
        Returns:
            API调用结果
            
        Raises:
            ResourceUnavailableError: 无法获取API资源
            ResourceTimeoutError: API调用超时
        """
        timeout = timeout or self.default_timeout
        limiter = self._get_limiter(api_name)
        semaphore = self._get_semaphore(api_name)
        
        # 更新使用统计
        self.usage_stats[api_name]["total_calls"] += 1
        self.usage_stats[api_name]["last_call_time"] = time.time()
        
        # 获取并发信号量
        try:
            async with asyncio.timeout(timeout):
                await semaphore.acquire()
        except asyncio.TimeoutError:
            self.usage_stats[api_name]["timeouts"] += 1
            logger.warning(f"获取API '{api_name}' 并发信号量超时 (timeout={timeout}秒)")
            raise ResourceTimeoutError(f"获取API '{api_name}' 并发信号量超时 (timeout={timeout}秒)")
        
        try:
            # 获取速率限制令牌
            if not await limiter.acquire(priority):
                self.usage_stats[api_name]["failed_calls"] += 1
                logger.warning(f"API '{api_name}' 速率限制拒绝请求")
                raise ResourceUnavailableError(f"API '{api_name}' 速率限制拒绝请求")
            
            # 执行API调用
            start_time = time.time()
            try:
                async with asyncio.timeout(timeout):
                    result = await call_func(*args, **kwargs)
                    
                # 更新响应时间统计
                response_time = time.time() - start_time
                self.usage_stats[api_name]["total_response_time"] += response_time
                completed_calls = (self.usage_stats[api_name]["total_calls"] - 
                                 self.usage_stats[api_name]["failed_calls"] - 
                                 self.usage_stats[api_name]["timeouts"])
                                 
                if completed_calls > 0:
                    self.usage_stats[api_name]["avg_response_time"] = (
                        self.usage_stats[api_name]["total_response_time"] / completed_calls
                    )
                    
                return result
                
            except asyncio.TimeoutError:
                self.usage_stats[api_name]["timeouts"] += 1
                logger.warning(f"API '{api_name}' 调用超时 (timeout={timeout}秒)")
                raise ResourceTimeoutError(f"API '{api_name}' 调用超时 (timeout={timeout}秒)")
                
            except Exception as e:
                self.usage_stats[api_name]["failed_calls"] += 1
                logger.error(f"API '{api_name}' 调用失败: {str(e)}")
                raise
                
        finally:
            # 释放信号量
            semaphore.release()
            
    async def reset_limiter(self, api_name: str):
        """
        重置API限制器
        
        Args:
            api_name: API名称
        """
        if api_name in self.limiters:
            async with self.locks[api_name]:
                self.limiters[api_name].reset()
                logger.info(f"已重置API '{api_name}' 限制器")
        else:
            logger.warning(f"尝试重置不存在的API限制器: {api_name}")
            
    async def set_rate_limit(self, api_name: str, calls: int, period: int):
        """
        设置API速率限制
        
        Args:
            api_name: API名称
            calls: 在period时间内允许的最大调用次数
            period: 时间窗口（秒）
        """
        if api_name in self.limiters:
            async with self.locks[api_name]:
                # 创建新的限制器
                self.limiters[api_name] = APIRateLimiter(api_name, calls, period)
                logger.info(f"更新API '{api_name}' 限制: {calls}次/{period}秒")
        else:
            # 创建新的限制器
            self._get_limiter(api_name)  # 使用默认值创建
            await self.set_rate_limit(api_name, calls, period)  # 递归调用设置新值 