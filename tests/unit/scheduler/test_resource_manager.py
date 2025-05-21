# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
ResourceManager单元测试。
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch

from src.taskflow.scheduler import (
    ResourceManager,
    ResourcePool,
    ResourceError,
    ResourceUnavailableError,
    ResourceTimeoutError
)


class TestResourcePool(ResourcePool):
    """测试用资源池实现"""
    
    def __init__(self, max_resources=10, fail_acquire=False, delay_acquire=0):
        self.max_resources = max_resources
        self.used_resources = 0
        self.fail_acquire = fail_acquire
        self.delay_acquire = delay_acquire
        self.acquire_calls = 0
        self.release_calls = 0
        self.lock = asyncio.Lock()
        
    async def acquire(self, amount=1, priority=0, timeout=None):
        """获取资源"""
        self.acquire_calls += 1
        
        # 模拟延迟
        if self.delay_acquire > 0:
            await asyncio.sleep(self.delay_acquire)
            
        # 模拟失败
        if self.fail_acquire:
            raise ResourceUnavailableError("测试资源获取失败")
            
        async with self.lock:
            if self.used_resources + amount > self.max_resources:
                raise ResourceUnavailableError(f"资源不足 (已用: {self.used_resources}, 请求: {amount}, 最大: {self.max_resources})")
                
            self.used_resources += amount
            return f"resource-{self.acquire_calls}"
            
    async def release(self, resource_handle):
        """释放资源"""
        self.release_calls += 1
        
        async with self.lock:
            if self.used_resources > 0:
                self.used_resources -= 1
                
    def get_status(self):
        """获取资源池状态"""
        return {
            "max_resources": self.max_resources,
            "used_resources": self.used_resources,
            "acquire_calls": self.acquire_calls,
            "release_calls": self.release_calls
        }


class TestResourceManager:
    """ResourceManager测试类"""
    
    @pytest.fixture
    async def resource_manager(self):
        """创建测试用资源管理器"""
        class TestingResourceManager(ResourceManager):
            """测试用资源管理器实现"""
            
            async def _initialize_resource_pools(self):
                """初始化测试资源池"""
                self.resource_pools["test_pool"] = TestResourcePool(max_resources=5)
                self.resource_pools["limited_pool"] = TestResourcePool(max_resources=1)
                self.resource_pools["failing_pool"] = TestResourcePool(fail_acquire=True)
                self.resource_pools["slow_pool"] = TestResourcePool(delay_acquire=0.5)
        
        manager = TestingResourceManager()
        await manager.initialize()
        return manager
        
    @pytest.mark.asyncio
    async def test_initialization(self, resource_manager):
        """测试资源管理器初始化"""
        # 验证初始化完成
        assert resource_manager.initialized
        
        # 验证资源池创建正确
        assert "test_pool" in resource_manager.resource_pools
        assert "limited_pool" in resource_manager.resource_pools
        assert "failing_pool" in resource_manager.resource_pools
        
        # 验证资源锁创建正确
        assert "test_pool" in resource_manager.locks
        assert "limited_pool" in resource_manager.locks
        assert "failing_pool" in resource_manager.locks
        
    @pytest.mark.asyncio
    async def test_acquire_resource(self, resource_manager):
        """测试获取资源"""
        # 获取资源
        resource = await resource_manager.acquire_resource("test_pool")
        
        # 验证资源获取成功
        assert resource is not None
        assert resource.startswith("resource-")
        
        # 验证资源池状态更新
        test_pool = resource_manager.resource_pools["test_pool"]
        assert test_pool.used_resources == 1
        assert test_pool.acquire_calls == 1
        
        # 释放资源
        await resource_manager.release_resource("test_pool", resource)
        
        # 验证资源释放成功
        assert test_pool.used_resources == 0
        assert test_pool.release_calls == 1
        
    @pytest.mark.asyncio
    async def test_acquire_with_priority(self, resource_manager):
        """测试带优先级的资源获取"""
        # 获取高优先级资源
        resource_high = await resource_manager.acquire_resource(
            "test_pool", priority=90
        )
        
        # 获取低优先级资源
        resource_low = await resource_manager.acquire_resource(
            "test_pool", priority=10
        )
        
        # 验证资源获取成功
        assert resource_high is not None
        assert resource_low is not None
        
        # 验证资源池状态
        test_pool = resource_manager.resource_pools["test_pool"]
        assert test_pool.used_resources == 2
        assert test_pool.acquire_calls == 2
        
        # 释放资源
        await resource_manager.release_resource("test_pool", resource_high)
        await resource_manager.release_resource("test_pool", resource_low)
        
    @pytest.mark.asyncio
    async def test_resource_unavailable(self, resource_manager):
        """测试资源不可用情况"""
        # 尝试获取已知会失败的资源池中的资源
        with pytest.raises(ResourceUnavailableError):
            await resource_manager.acquire_resource("failing_pool")
            
        # 验证调用了资源池的acquire方法
        failing_pool = resource_manager.resource_pools["failing_pool"]
        assert failing_pool.acquire_calls == 1
        assert failing_pool.used_resources == 0
        
    @pytest.mark.asyncio
    async def test_resource_timeout(self, resource_manager):
        """测试资源获取超时"""
        # 设置非常短的超时时间获取慢速资源池中的资源
        with pytest.raises(ResourceTimeoutError):
            await resource_manager.acquire_resource("slow_pool", timeout=0.1)
            
        # 验证资源池状态
        slow_pool = resource_manager.resource_pools["slow_pool"]
        assert slow_pool.acquire_calls >= 1
        assert slow_pool.used_resources == 0
        
    @pytest.mark.asyncio
    async def test_resource_exhaustion(self, resource_manager):
        """测试资源耗尽情况"""
        # 限制资源池只有1个资源
        limited_pool = resource_manager.resource_pools["limited_pool"]
        
        # 获取唯一的资源
        resource = await resource_manager.acquire_resource("limited_pool")
        assert resource is not None
        assert limited_pool.used_resources == 1
        
        # 尝试获取更多资源应该失败
        with pytest.raises(ResourceUnavailableError):
            await resource_manager.acquire_resource("limited_pool", timeout=0.1)
            
        # 释放资源后应该可以再次获取
        await resource_manager.release_resource("limited_pool", resource)
        assert limited_pool.used_resources == 0
        
        resource_again = await resource_manager.acquire_resource("limited_pool")
        assert resource_again is not None
        assert limited_pool.used_resources == 1
        
        # 清理
        await resource_manager.release_resource("limited_pool", resource_again)
        
    @pytest.mark.asyncio
    async def test_unknown_resource_type(self, resource_manager):
        """测试未知资源类型"""
        with pytest.raises(ResourceUnavailableError):
            await resource_manager.acquire_resource("nonexistent_pool")
            
    @pytest.mark.asyncio
    async def test_with_resource_context(self, resource_manager):
        """测试资源上下文管理器"""
        test_pool = resource_manager.resource_pools["test_pool"]
        initial_used = test_pool.used_resources
        
        # 使用上下文管理器获取资源
        async with resource_manager.with_resource("test_pool") as resource:
            assert resource is not None
            assert test_pool.used_resources == initial_used + 1
            
        # 上下文退出后资源应该自动释放
        assert test_pool.used_resources == initial_used
        
    @pytest.mark.asyncio
    async def test_get_resource_status(self, resource_manager):
        """测试获取资源状态"""
        # 获取状态
        status = resource_manager.get_resource_status()
        
        # 验证状态包含所有资源池
        assert "test_pool" in status
        assert "limited_pool" in status
        assert "failing_pool" in status
        assert "slow_pool" in status
        
        # 验证状态内容
        assert "max_resources" in status["test_pool"]
        assert "used_resources" in status["test_pool"]
        assert status["test_pool"]["max_resources"] == 5 