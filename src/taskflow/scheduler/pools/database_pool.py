# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
数据库资源池模块。

提供数据库连接的资源管理，包括连接池维护、连接复用及监控。
"""

import time
import asyncio
import logging
from typing import Dict, Any, Optional, List, Union

from ..resource import ResourcePool, ResourceUnavailableError, ResourceTimeoutError

# 获取logger
logger = logging.getLogger(__name__)


class DatabaseConnection:
    """数据库连接包装类"""
    
    def __init__(self, connection_id: str):
        self.connection_id = connection_id
        self.created_at = time.time()
        self.last_used_at = time.time()
        self.is_in_use = False
        self.total_usage_count = 0
        # 实际项目中这里会包含真实的数据库连接
        # self.connection = real_db_connection
        
    def __str__(self):
        return f"DBConn({self.connection_id}, active={self.is_in_use})"
        
    def mark_as_used(self):
        """标记连接被使用"""
        self.is_in_use = True
        self.last_used_at = time.time()
        self.total_usage_count += 1
        
    def mark_as_free(self):
        """标记连接为空闲"""
        self.is_in_use = False
        self.last_used_at = time.time()


class DatabaseResourcePool(ResourcePool):
    """数据库连接资源池实现"""
    
    def __init__(self, max_connections: int = 20, idle_timeout: int = 300, 
                 max_age: int = 3600, acquire_timeout: float = 10):
        """
        初始化数据库资源池
        
        Args:
            max_connections: 最大连接数
            idle_timeout: 空闲连接超时时间（秒）
            max_age: 连接最大生存时间（秒）
            acquire_timeout: 默认获取超时时间（秒）
        """
        self.max_connections = max_connections
        self.idle_timeout = idle_timeout
        self.max_age = max_age
        self.default_timeout = acquire_timeout
        
        self.connections = {}  # 所有连接
        self.free_connections = []  # 空闲连接ID列表
        self.connection_lock = asyncio.Lock()
        self.cleanup_task = None
        
        self.usage_stats = {
            "total_connections_created": 0,
            "total_connections_closed": 0,
            "connection_timeouts": 0,
            "peak_connections": 0,
        }
        
        logger.info(f"数据库资源池初始化: 最大连接数={max_connections}, "
                   f"空闲超时={idle_timeout}秒, 最大生存期={max_age}秒")
        
    async def start_cleanup_task(self):
        """启动清理任务"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.debug("启动数据库连接清理任务")
            
    async def _cleanup_loop(self):
        """定期清理过期连接"""
        try:
            while True:
                await asyncio.sleep(min(self.idle_timeout // 3, 60))  # 最多每60秒检查一次
                await self._cleanup_expired_connections()
        except asyncio.CancelledError:
            logger.debug("数据库连接清理任务已取消")
        except Exception as e:
            logger.error(f"数据库连接清理任务出错: {str(e)}")
            
    async def _cleanup_expired_connections(self):
        """清理过期连接"""
        now = time.time()
        to_close = []
        
        async with self.connection_lock:
            # 找出需要关闭的连接
            for conn_id, conn in list(self.connections.items()):
                # 跳过正在使用的连接
                if conn.is_in_use:
                    continue
                    
                # 检查空闲超时
                if now - conn.last_used_at > self.idle_timeout:
                    to_close.append(conn_id)
                    logger.debug(f"连接空闲超时: {conn}")
                    continue
                    
                # 检查最大生存期
                if now - conn.created_at > self.max_age:
                    to_close.append(conn_id)
                    logger.debug(f"连接达到最大生存期: {conn}")
                    continue
        
        # 关闭过期连接
        for conn_id in to_close:
            await self._close_connection(conn_id)
            
    async def _close_connection(self, connection_id: str):
        """关闭连接"""
        async with self.connection_lock:
            if connection_id in self.connections:
                conn = self.connections[connection_id]
                # 实际项目中这里会关闭真实的数据库连接
                # await conn.connection.close()
                
                # 从池中移除
                del self.connections[connection_id]
                if connection_id in self.free_connections:
                    self.free_connections.remove(connection_id)
                    
                self.usage_stats["total_connections_closed"] += 1
                logger.debug(f"关闭数据库连接: {conn}")
        
    async def _create_connection(self) -> str:
        """创建新连接"""
        connection_id = f"db-{int(time.time() * 1000)}-{self.usage_stats['total_connections_created']}"
        
        # 实际项目中这里会创建真实的数据库连接
        # real_connection = await create_real_db_connection()
        
        # 创建连接包装对象
        connection = DatabaseConnection(connection_id)
        
        # 添加到连接池
        self.connections[connection_id] = connection
        self.free_connections.append(connection_id)
        
        self.usage_stats["total_connections_created"] += 1
        current_count = len(self.connections)
        if current_count > self.usage_stats["peak_connections"]:
            self.usage_stats["peak_connections"] = current_count
            
        logger.debug(f"创建新数据库连接: {connection}")
        return connection_id
        
    async def acquire(self, amount: int = 1, priority: int = 0, 
                     timeout: Optional[float] = None) -> Any:
        """
        获取数据库连接
        
        Args:
            amount: 请求连接数量（通常为1）
            priority: 优先级（0-100）
            timeout: 超时时间（秒）
            
        Returns:
            连接ID
            
        Raises:
            ResourceUnavailableError: 无法获取连接
            ResourceTimeoutError: 获取连接超时
        """
        if amount != 1:
            logger.warning(f"数据库连接池不支持批量获取，忽略amount={amount}，只返回1个连接")
            
        timeout = timeout or self.default_timeout
        
        # 启动清理任务（如果未启动）
        await self.start_cleanup_task()
        
        try:
            # 设置超时
            start_time = time.time()
            while time.time() - start_time < timeout:
                # 尝试获取空闲连接或创建新连接
                connection_id = await self._get_connection(priority)
                if connection_id:
                    return connection_id
                    
                # 没有可用连接，等待一小段时间
                await asyncio.sleep(0.1)
                
            # 超时
            self.usage_stats["connection_timeouts"] += 1
            logger.warning(f"获取数据库连接超时 (timeout={timeout}秒)")
            raise ResourceTimeoutError(f"获取数据库连接超时 (timeout={timeout}秒)")
            
        except asyncio.CancelledError:
            logger.debug("获取数据库连接操作被取消")
            raise
            
    async def _get_connection(self, priority: int) -> Optional[str]:
        """获取可用连接或创建新连接"""
        async with self.connection_lock:
            # 首先尝试获取空闲连接
            if self.free_connections:
                connection_id = self.free_connections.pop(0)
                conn = self.connections[connection_id]
                conn.mark_as_used()
                logger.debug(f"复用空闲数据库连接: {conn}")
                return connection_id
                
            # 如果没有空闲连接但未达到最大连接数，创建新连接
            if len(self.connections) < self.max_connections:
                connection_id = await self._create_connection()
                conn = self.connections[connection_id]
                
                # 从空闲列表中移除并标记为使用中
                self.free_connections.remove(connection_id)
                conn.mark_as_used()
                
                return connection_id
                
            # 如果是高优先级请求，尝试释放最老的空闲连接
            if priority >= 80 and self.connections:
                # 找到最老的连接（最后使用时间最早的）
                oldest_conn_id = None
                oldest_time = float('inf')
                
                for conn_id, conn in self.connections.items():
                    if not conn.is_in_use and conn.last_used_at < oldest_time:
                        oldest_conn_id = conn_id
                        oldest_time = conn.last_used_at
                
                if oldest_conn_id:
                    # 关闭并移除最老的连接
                    await self._close_connection(oldest_conn_id)
                    
                    # 创建新连接
                    connection_id = await self._create_connection()
                    conn = self.connections[connection_id]
                    
                    # 从空闲列表中移除并标记为使用中
                    self.free_connections.remove(connection_id)
                    conn.mark_as_used()
                    
                    logger.info(f"高优先级请求({priority})释放了最老的连接并创建新连接: {conn}")
                    return connection_id
            
            # 没有可用连接
            return None
        
    async def release(self, connection_id: str) -> None:
        """
        释放数据库连接
        
        Args:
            connection_id: 连接ID
        """
        async with self.connection_lock:
            if connection_id in self.connections:
                conn = self.connections[connection_id]
                conn.mark_as_free()
                self.free_connections.append(connection_id)
                logger.debug(f"释放数据库连接: {conn}")
            else:
                logger.warning(f"尝试释放不存在的数据库连接: {connection_id}")
        
    def get_status(self) -> Dict[str, Any]:
        """
        获取资源池状态
        
        Returns:
            资源状态字典
        """
        return {
            "type": "database",
            "max_connections": self.max_connections,
            "current_connections": len(self.connections),
            "free_connections": len(self.free_connections),
            "usage_stats": self.usage_stats
        }
        
    async def shutdown(self):
        """关闭连接池"""
        logger.info("关闭数据库连接池")
        
        # 取消清理任务
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有连接
        for conn_id in list(self.connections.keys()):
            await self._close_connection(conn_id) 