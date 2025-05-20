# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
LLM资源池模块。

提供LLM API调用的资源管理，包括并发限制、速率限制和统计功能。
"""

import time
import asyncio
import logging
from collections import deque
from typing import Dict, Any, Optional, List

from ..resource import ResourcePool, ResourceUnavailableError, ResourceTimeoutError

# 获取logger
logger = logging.getLogger(__name__)


class LLMResourcePool(ResourcePool):
    """LLM API资源池实现"""
    
    def __init__(self, max_concurrent: int = 5, rate_limit: int = 10, 
                 time_window: int = 60, timeout: float = 30):
        """
        初始化LLM资源池
        
        Args:
            max_concurrent: 最大并发请求数
            rate_limit: 在time_window时间窗口内的最大请求数
            time_window: 速率限制的时间窗口（秒）
            timeout: 默认超时时间（秒）
        """
        self.max_concurrent = max_concurrent
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.default_timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.request_times = deque(maxlen=rate_limit)
        self.usage_stats = {
            "total_requests": 0,
            "failed_requests": 0,
            "timeouts": 0,
            "avg_response_time": 0,
            "total_response_time": 0,
        }
        logger.info(f"LLM资源池初始化: 最大并发={max_concurrent}, "
                   f"速率限制={rate_limit}/{time_window}秒")
        
    async def acquire(self, amount: int = 1, priority: int = 0, 
                     timeout: Optional[float] = None) -> Any:
        """
        获取LLM API资源
        
        Args:
            amount: 请求数量（对LLM通常为1）
            priority: 优先级（0-100）
            timeout: 超时时间（秒）
            
        Returns:
            资源句柄（为LLM池返回请求ID）
            
        Raises:
            ResourceUnavailableError: 资源不可用
            ResourceTimeoutError: 获取资源超时
        """
        timeout = timeout or self.default_timeout
        request_id = f"llm-{int(time.time() * 1000)}-{self.usage_stats['total_requests']}"
        
        # 检查速率限制
        now = time.time()
        if len(self.request_times) == self.rate_limit:
            oldest = self.request_times[0]
            time_diff = now - oldest
            if time_diff < self.time_window:
                wait_time = self.time_window - time_diff
                if priority < 80:  # 高优先级任务可以突破限制
                    logger.debug(f"请求 {request_id} 等待速率限制: {wait_time}秒")
                    # 等待足够时间
                    await asyncio.sleep(wait_time)
                else:
                    # 记录等待但不实际等待
                    logger.info(f"高优先级任务({priority})突破了速率限制: {request_id}")
        
        # 尝试获取信号量
        try:
            acquired = await asyncio.wait_for(
                self.semaphore.acquire(),
                timeout=timeout
            )
            if not acquired:
                raise ResourceUnavailableError(f"无法获取LLM资源: {request_id}")
                
            # 记录请求时间和统计信息
            self.request_times.append(now)
            self.usage_stats["total_requests"] += 1
            logger.debug(f"成功获取LLM资源: {request_id}")
            
            # 返回请求ID作为资源句柄
            return request_id
            
        except asyncio.TimeoutError:
            self.usage_stats["timeouts"] += 1
            logger.warning(f"获取LLM资源超时: {request_id} (timeout={timeout}秒)")
            raise ResourceTimeoutError(f"获取LLM资源超时 (timeout={timeout}秒): {request_id}")
        
    async def release(self, resource_handle: Any) -> None:
        """
        释放LLM API资源
        
        Args:
            resource_handle: 资源句柄（请求ID）
        """
        self.semaphore.release()
        logger.debug(f"释放LLM资源: {resource_handle}")
        
    def get_status(self) -> Dict[str, Any]:
        """
        获取资源池状态
        
        Returns:
            资源状态字典
        """
        return {
            "type": "llm",
            "max_concurrent": self.max_concurrent,
            "available": self.semaphore._value,
            "rate_limit": self.rate_limit,
            "time_window": self.time_window,
            "current_rate": len(self.request_times),
            "usage_stats": self.usage_stats
        }
        
    def update_usage_stats(self, request_id: str, success: bool, response_time: float):
        """
        更新使用统计信息
        
        Args:
            request_id: 请求ID
            success: 请求是否成功
            response_time: 响应时间（秒）
        """
        if not success:
            self.usage_stats["failed_requests"] += 1
            
        self.usage_stats["total_response_time"] += response_time
        
        # 计算平均响应时间
        total_completed = (self.usage_stats["total_requests"] - 
                           self.usage_stats["timeouts"])
        if total_completed > 0:
            self.usage_stats["avg_response_time"] = (
                self.usage_stats["total_response_time"] / total_completed
            ) 