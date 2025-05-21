# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow数据验证模块。

提供数据验证功能，确保输入数据符合要求。
"""

import logging
import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Type, TypeVar, Callable

from pydantic import BaseModel, Field, validator, root_validator
from pydantic.error_wrappers import ValidationError

from src.taskflow.exceptions import ObjectiveValidationError, TaskValidationError, StepValidationError

# 获取日志记录器
logger = logging.getLogger(__name__)

# 类型变量
T = TypeVar('T')


class StatusEnum(str, Enum):
    """状态枚举类型"""
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskTypeEnum(str, Enum):
    """任务类型枚举"""
    RESEARCH = "RESEARCH"
    PROCESSING = "PROCESSING"
    ANALYSIS = "ANALYSIS"
    SYNTHESIS = "SYNTHESIS"
    GENERIC = "GENERIC"


class StepTypeEnum(str, Enum):
    """步骤类型枚举"""
    DATA_COLLECTION = "DATA_COLLECTION"
    DOCUMENT_ANALYSIS = "DOCUMENT_ANALYSIS"
    WEB_SEARCH = "WEB_SEARCH"
    CALCULATION = "CALCULATION"
    SUMMARY = "SUMMARY"
    REPORT = "REPORT"
    GENERIC = "GENERIC"


class ObjectiveCreate(BaseModel):
    """创建目标的验证模型"""
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    query: str = Field(..., min_length=5, max_length=1000)
    priority: Optional[int] = Field(0, ge=0, le=10)
    user_id: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @validator('title')
    def title_not_empty(cls, v):
        """验证标题不为空"""
        v = v.strip()
        if not v:
            raise ValueError('标题不能为空')
        return v
    
    @validator('query')
    def query_not_empty(cls, v):
        """验证查询不为空"""
        v = v.strip()
        if not v:
            raise ValueError('查询不能为空')
        return v


class TaskCreate(BaseModel):
    """创建任务的验证模型"""
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    task_type: TaskTypeEnum
    priority: Optional[int] = Field(0, ge=0, le=10)
    objective_id: str
    parent_task_id: Optional[str] = None
    depends_on: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @validator('title')
    def title_not_empty(cls, v):
        """验证标题不为空"""
        v = v.strip()
        if not v:
            raise ValueError('标题不能为空')
        return v
    
    @validator('depends_on')
    def dependencies_not_self(cls, v, values):
        """验证依赖不包含自身"""
        if v is not None and 'id' in values and values['id'] in v:
            raise ValueError('任务不能依赖自身')
        return v


class StepCreate(BaseModel):
    """创建步骤的验证模型"""
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    step_type: StepTypeEnum
    priority: Optional[int] = Field(0, ge=0, le=10)
    task_id: str
    agent_type: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    
    @validator('name')
    def name_not_empty(cls, v):
        """验证名称不为空"""
        v = v.strip()
        if not v:
            raise ValueError('名称不能为空')
        return v


class WorkflowCreate(BaseModel):
    """创建工作流的验证模型"""
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    workflow_type: str = Field(..., min_length=1, max_length=50)
    objective_id: Optional[str] = None
    task_id: Optional[str] = None
    state: Optional[Dict[str, Any]] = None
    
    @validator('name')
    def name_not_empty(cls, v):
        """验证名称不为空"""
        v = v.strip()
        if not v:
            raise ValueError('名称不能为空')
        return v
    
    @root_validator(skip_on_failure=True)
    def check_objective_or_task(cls, values):
        """验证目标ID或任务ID至少有一个"""
        if not values.get('objective_id') and not values.get('task_id'):
            raise ValueError('必须提供目标ID或任务ID')
        return values


def validate_model(model_class: Type[BaseModel], data: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用Pydantic模型验证数据。
    
    Args:
        model_class: Pydantic模型类
        data: 输入数据
        
    Returns:
        验证后的数据
        
    Raises:
        ObjectiveValidationError: 目标验证失败
        TaskValidationError: 任务验证失败
        StepValidationError: 步骤验证失败
    """
    try:
        validated_data = model_class(**data)
        return validated_data.dict()
    except ValidationError as e:
        # 根据模型类型选择适当的异常
        model_name = model_class.__name__
        error_msg = f"{model_name}验证失败: {str(e)}"
        
        if model_name.startswith("Objective"):
            raise ObjectiveValidationError(error_msg)
        elif model_name.startswith("Task"):
            raise TaskValidationError(error_msg)
        elif model_name.startswith("Step"):
            raise StepValidationError(error_msg)
        else:
            raise ValueError(error_msg)


def validate_id(id_value: str, name: str = "ID") -> str:
    """
    验证ID格式是否有效。
    
    Args:
        id_value: ID值
        name: ID名称（用于错误消息）
        
    Returns:
        验证后的ID
        
    Raises:
        ValueError: ID格式无效
    """
    if not id_value:
        raise ValueError(f"{name}不能为空")
    
    # UUID格式验证
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    uuid_alt_pattern = r'^[0-9a-f]{32}$'
    
    if not (re.match(uuid_pattern, id_value, re.I) or re.match(uuid_alt_pattern, id_value, re.I)):
        # 如果不是严格的UUID格式，检查是否是有效的字符串格式
        if not re.match(r'^[a-z0-9_-]{1,36}$', id_value, re.I):
            raise ValueError(f"{name}格式无效")
    
    return id_value


def validate_status(status: str, valid_statuses: Set[str] = None) -> str:
    """
    验证状态值是否有效。
    
    Args:
        status: 状态值
        valid_statuses: 有效状态集合（默认使用StatusEnum）
        
    Returns:
        验证后的状态
        
    Raises:
        ValueError: 状态值无效
    """
    if not status:
        raise ValueError("状态不能为空")
    
    if valid_statuses is None:
        valid_statuses = {s.value for s in StatusEnum}
    
    if status not in valid_statuses:
        raise ValueError(f"无效的状态值: {status}，有效值为: {', '.join(valid_statuses)}")
    
    return status


def validate_priority(priority: int) -> int:
    """
    验证优先级值是否有效。
    
    Args:
        priority: 优先级值
        
    Returns:
        验证后的优先级
        
    Raises:
        ValueError: 优先级值无效
    """
    if not isinstance(priority, int):
        raise ValueError("优先级必须是整数")
    
    if priority < 0 or priority > 10:
        raise ValueError("优先级必须在0-10范围内")
    
    return priority


def validate_with_function(value: T, validator_func: Callable[[T], T], error_msg: str = None) -> T:
    """
    使用自定义函数验证值。
    
    Args:
        value: 要验证的值
        validator_func: 验证函数
        error_msg: 错误消息
        
    Returns:
        验证后的值
        
    Raises:
        ValueError: 验证失败
    """
    try:
        return validator_func(value)
    except Exception as e:
        if error_msg:
            raise ValueError(error_msg) from e
        raise ValueError(f"验证失败: {str(e)}") from e 