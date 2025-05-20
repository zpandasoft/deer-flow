# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""API依赖注入模块。

该模块提供API端点使用的依赖注入函数，用于获取服务实例。
"""

from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.taskflow.db.base import get_async_session
from src.taskflow.db.service import DatabaseService
from src.taskflow.scheduler.scheduler import TaskScheduler, get_scheduler
from src.taskflow.graph.builder import WorkflowService, get_workflow_service


async def get_db() -> Generator[DatabaseService, None, None]:
    """获取数据库服务实例。
    
    依赖注入函数，用于在API端点中获取数据库服务实例。
    
    Yields:
        DatabaseService: 数据库服务实例
    """
    session: AsyncSession = await get_async_session()
    try:
        db = DatabaseService(session)
        yield db
    finally:
        await session.close()


def get_scheduler_service() -> TaskScheduler:
    """获取任务调度器实例。
    
    依赖注入函数，用于在API端点中获取任务调度器实例。
    
    Returns:
        TaskScheduler: 任务调度器实例
    """
    return get_scheduler()


def get_workflow_svc() -> WorkflowService:
    """获取工作流服务实例。
    
    依赖注入函数，用于在API端点中获取工作流服务实例。
    
    Returns:
        WorkflowService: 工作流服务实例
    """
    return get_workflow_service()


# API权限相关的依赖（如果需要）
async def verify_api_key(api_key: Optional[str] = None) -> bool:
    """验证API密钥。
    
    如果配置了API密钥认证，则验证请求中的API密钥是否有效。
    
    Args:
        api_key: API密钥
        
    Returns:
        bool: 验证是否通过
        
    Raises:
        HTTPException: 当API密钥无效时
    """
    # TODO: 实现API密钥验证逻辑，当前版本返回True表示验证通过
    if api_key is None:
        return True
    
    # 此处实现真正的API密钥验证逻辑
    is_valid = True  # 示例值，实际实现应该验证密钥
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的API密钥",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return True 