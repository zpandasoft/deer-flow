# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""API依赖注入模块。

该模块提供API端点使用的依赖注入函数，用于获取服务实例。
"""

from typing import Generator, Optional, Dict, Any

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.taskflow.db.base import get_db_session
from src.taskflow.scheduler.scheduler import TaskScheduler


# 工作流服务类定义
class WorkflowService:
    """工作流服务类。
    
    处理工作流创建、执行和管理。
    """
    
    def __init__(self):
        """初始化工作流服务。"""
        self.workflows = {}
    
    def create_workflow(self, workflow_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新工作流。
        
        Args:
            workflow_type: 工作流类型
            data: 工作流数据
            
        Returns:
            创建的工作流信息
        """
        # 简单实现，实际项目中会有更复杂的逻辑
        workflow_id = data.get("id", f"workflow-{len(self.workflows) + 1}")
        self.workflows[workflow_id] = {
            "id": workflow_id,
            "type": workflow_type,
            "data": data,
            "status": "CREATED"
        }
        return self.workflows[workflow_id]
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """获取工作流信息。
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            工作流信息或None
        """
        return self.workflows.get(workflow_id)


# 单例工作流服务实例
_workflow_service_instance = None


def get_workflow_svc() -> WorkflowService:
    """获取工作流服务实例。
    
    依赖注入函数，用于在API端点中获取工作流服务实例。
    
    Returns:
        WorkflowService: 工作流服务实例
    """
    global _workflow_service_instance
    if _workflow_service_instance is None:
        _workflow_service_instance = WorkflowService()
    return _workflow_service_instance


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话实例。
    
    依赖注入函数，用于在API端点中获取数据库会话实例。
    
    Yields:
        Session: 数据库会话实例
    """
    session = get_db_session()
    try:
        yield session
    finally:
        session.close()


def get_scheduler_service() -> TaskScheduler:
    """获取任务调度器实例。
    
    依赖注入函数，用于在API端点中获取任务调度器实例。
    
    Returns:
        TaskScheduler: 任务调度器实例
    """
    # 创建一个新的调度器实例
    scheduler = TaskScheduler()
    return scheduler


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