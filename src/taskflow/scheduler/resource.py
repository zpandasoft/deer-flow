# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
资源管理器模块，负责系统资源的分配和监控。

此模块提供集中式资源管理功能，包括LLM API调用、数据库连接、工作线程等资源的
分配、回收和监控。
"""

import asyncio
import time
import logging
from abc import ABC, abstractmethod
from collections import deque
from typing import Dict, Any, Optional, List, Union, Tuple

from ..exceptions import TaskflowError

# 获取logger
logger = logging.getLogger(__name__)


class ResourceError(TaskflowError):
    """资源管理相关异常基类"""
    pass


class ResourceUnavailableError(ResourceError):
    """资源不可用异常"""
    pass


class UnknownResourceTypeError(ResourceError):
    """未知资源类型异常"""
    pass


class ResourceTimeoutError(ResourceError):
    """资源获取超时异常"""
    pass


class ResourcePool(ABC):
    """资源池抽象基类"""
    
    @abstractmethod
    async def acquire(self, amount: int = 1, priority: int = 0, timeout: float = None) -> Any:
        """
        获取资源
        
        Args:
            amount: 请求资源数量
            priority: 请求优先级（0-100，越高优先级越高）
            timeout: 获取超时时间（秒）
            
        Returns:
            资源句柄或标识符
            
        Raises:
            ResourceUnavailableError: 无法获取资源
            ResourceTimeoutError: 获取资源超时
        """
        pass
        
    @abstractmethod
    async def release(self, resource_handle: Any) -> None:
        """
        释放资源
        
        Args:
            resource_handle: 资源句柄或标识符
        """
        pass
        
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        获取资源池状态
        
        Returns:
            资源状态字典
        """
        pass


class ResourceManager:
    """资源管理器，负责系统资源的分配和监控"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化资源管理器
        
        Args:
            config: 资源配置字典，默认为None（使用默认配置）
        """
        self.config = config or {}
        self.resource_pools = {}
        self.locks = {}
        self.logger = logger
        self.initialized = False
        
    async def initialize(self):
        """异步初始化资源池"""
        if self.initialized:
            return
            
        # 初始化资源池
        await self._initialize_resource_pools()
        
        # 为每个资源池创建锁
        for pool_name in self.resource_pools:
            self.locks[pool_name] = asyncio.Lock()
            
        self.initialized = True
        self.logger.info("ResourceManager初始化完成")
    
    async def _initialize_resource_pools(self):
        """初始化各类资源池"""
        # 这里将在具体实现中添加各类资源池
        # 在子类中实现或后续扩展
        pass
    
    async def _ensure_initialized(self):
        """确保资源管理器已初始化"""
        if not self.initialized:
            await self.initialize()
    
    async def acquire_resource(self, resource_type: str, 
                              amount: int = 1, 
                              priority: int = 0, 
                              timeout: Optional[float] = None) -> Any:
        """
        获取指定类型的资源
        
        Args:
            resource_type: 资源类型
            amount: 请求资源数量
            priority: 请求优先级（0-100，越高优先级越高）
            timeout: 获取超时时间（秒）
            
        Returns:
            资源句柄或标识符
            
        Raises:
            ResourceUnavailableError: 无法获取资源
            UnknownResourceTypeError: 未知资源类型
            ResourceTimeoutError: 获取资源超时
        """
        await self._ensure_initialized()
        
        if resource_type not in self.resource_pools:
            raise UnknownResourceTypeError(f"未知资源类型: {resource_type}")
            
        async with self.locks[resource_type]:
            try:
                self.logger.debug(f"尝试获取资源: {resource_type}, 数量: {amount}, 优先级: {priority}")
                resource = await self.resource_pools[resource_type].acquire(
                    amount=amount,
                    priority=priority,
                    timeout=timeout
                )
                self.logger.debug(f"成功获取资源: {resource_type}")
                return resource
            except Exception as e:
                self.logger.error(f"获取资源失败: {resource_type}, 错误: {str(e)}")
                raise
    
    async def release_resource(self, resource_type: str, resource_handle: Any):
        """
        释放指定类型的资源
        
        Args:
            resource_type: 资源类型
            resource_handle: 资源句柄或标识符
            
        Raises:
            UnknownResourceTypeError: 未知资源类型
        """
        await self._ensure_initialized()
        
        if resource_type not in self.resource_pools:
            raise UnknownResourceTypeError(f"未知资源类型: {resource_type}")
            
        async with self.locks[resource_type]:
            try:
                self.logger.debug(f"释放资源: {resource_type}")
                await self.resource_pools[resource_type].release(resource_handle)
            except Exception as e:
                self.logger.error(f"释放资源失败: {resource_type}, 错误: {str(e)}")
                raise
            
    def get_resource_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取各资源池状态
        
        Returns:
            资源状态字典，格式为: {resource_type: {status_info}}
        """
        if not self.initialized:
            return {"status": "未初始化"}
            
        status = {}
        for pool_name, pool in self.resource_pools.items():
            status[pool_name] = pool.get_status()
        return status
        
    async def with_resource(self, resource_type: str, 
                           amount: int = 1, 
                           priority: int = 0,
                           timeout: Optional[float] = None):
        """
        资源上下文管理器
        
        使用示例:
        ```
        async with resource_manager.with_resource("llm") as llm_resource:
            # 使用资源...
            result = await use_llm(llm_resource)
        # 资源自动释放
        ```
        
        Args:
            resource_type: 资源类型
            amount: 请求资源数量
            priority: 请求优先级
            timeout: 获取超时时间
            
        Yields:
            资源句柄或标识符
        """
        resource = await self.acquire_resource(
            resource_type, amount, priority, timeout
        )
        try:
            yield resource
        finally:
            await self.release_resource(resource_type, resource) 