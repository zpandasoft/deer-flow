# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow数据库模式模块。

提供Pydantic模型用于数据验证和API序列化。
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, Field, validator


# 基础模型
class BaseSchema(BaseModel):
    """所有模式的基类，提供共同字段和方法"""
    
    class Config:
        """配置类"""
        orm_mode = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


# 目标模型
class ObjectiveBase(BaseSchema):
    """目标基本属性"""
    title: str
    description: Optional[str] = None
    query: str
    priority: Optional[int] = 0
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class ObjectiveCreate(ObjectiveBase):
    """创建目标时使用的模式"""
    pass


class ObjectiveUpdate(BaseSchema):
    """更新目标时使用的模式"""
    title: Optional[str] = None
    description: Optional[str] = None
    query: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class ObjectiveInDB(ObjectiveBase):
    """数据库中的目标模式"""
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class Objective(ObjectiveInDB):
    """完整目标模式"""
    pass


# 任务模型
class TaskBase(BaseSchema):
    """任务基本属性"""
    title: str
    description: Optional[str] = None
    task_type: str
    priority: Optional[int] = 0
    objective_id: str
    parent_task_id: Optional[str] = None
    depends_on: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskCreate(TaskBase):
    """创建任务时使用的模式"""
    pass


class TaskUpdate(BaseSchema):
    """更新任务时使用的模式"""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None


class TaskInDB(TaskBase):
    """数据库中的任务模式"""
    id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class Task(TaskInDB):
    """完整任务模式"""
    pass


# 步骤模型
class StepBase(BaseSchema):
    """步骤基本属性"""
    name: str
    description: Optional[str] = None
    step_type: str
    priority: Optional[int] = 0
    task_id: str
    agent_type: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None


class StepCreate(StepBase):
    """创建步骤时使用的模式"""
    pass


class StepUpdate(BaseSchema):
    """更新步骤时使用的模式"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    agent_type: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class StepInDB(StepBase):
    """数据库中的步骤模式"""
    id: str
    status: str
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Step(StepInDB):
    """完整步骤模式"""
    pass


# 工作流模型
class WorkflowBase(BaseSchema):
    """工作流基本属性"""
    name: str
    description: Optional[str] = None
    workflow_type: str
    objective_id: Optional[str] = None
    task_id: Optional[str] = None


class WorkflowCreate(WorkflowBase):
    """创建工作流时使用的模式"""
    pass


class WorkflowUpdate(BaseSchema):
    """更新工作流时使用的模式"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    current_node: Optional[str] = None
    is_paused: Optional[bool] = None
    state: Optional[Dict[str, Any]] = None


class WorkflowInDB(WorkflowBase):
    """数据库中的工作流模式"""
    id: str
    status: str
    current_node: Optional[str] = None
    is_paused: bool
    state: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Workflow(WorkflowInDB):
    """完整工作流模式"""
    pass


# 工作流检查点模型
class WorkflowCheckpointBase(BaseSchema):
    """工作流检查点基本属性"""
    name: str
    node_name: str
    workflow_id: str
    state: Dict[str, Any]


class WorkflowCheckpointCreate(WorkflowCheckpointBase):
    """创建工作流检查点时使用的模式"""
    pass


class WorkflowCheckpointInDB(WorkflowCheckpointBase):
    """数据库中的工作流检查点模式"""
    id: str
    created_at: datetime


class WorkflowCheckpoint(WorkflowCheckpointInDB):
    """完整工作流检查点模式"""
    pass 