# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""API请求和响应模型定义。

该模块定义了API接口使用的请求和响应数据模型，用于数据验证和API文档生成。
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union

from pydantic import BaseModel, Field, validator


class StatusEnum(str, Enum):
    """任务和目标的状态枚举"""
    CREATED = "CREATED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PriorityEnum(int, Enum):
    """优先级枚举"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


# 请求模型
class ObjectiveCreate(BaseModel):
    """创建研究目标的请求模型"""
    query: str = Field(..., description="用户查询/研究目标描述")
    description: Optional[str] = Field(None, description="目标详细描述")
    user_id: Optional[str] = Field(None, description="用户ID")
    priority: Optional[PriorityEnum] = Field(PriorityEnum.MEDIUM, description="目标优先级")
    tags: Optional[List[str]] = Field(None, description="目标标签")
    
    @validator('query')
    def query_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('查询不能为空')
        return v


class TaskFilter(BaseModel):
    """任务过滤条件"""
    status: Optional[StatusEnum] = None
    priority: Optional[PriorityEnum] = None
    tags: Optional[List[str]] = None


class StepSchedule(BaseModel):
    """调度步骤执行的请求模型"""
    step_ids: List[str] = Field(..., description="要调度的步骤ID列表")
    priority: Optional[PriorityEnum] = Field(PriorityEnum.MEDIUM, description="调度优先级")


# 响应模型
class ObjectiveResponse(BaseModel):
    """目标创建响应"""
    objective_id: str = Field(..., description="创建的目标ID")
    status: StatusEnum = Field(..., description="目标状态")


class ObjectiveDetail(BaseModel):
    """目标详细信息"""
    id: str = Field(..., description="目标ID")
    title: str = Field(..., description="目标标题")
    description: Optional[str] = Field(None, description="目标详细描述")
    status: StatusEnum = Field(..., description="目标状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    user_id: Optional[str] = Field(None, description="用户ID")
    priority: PriorityEnum = Field(..., description="目标优先级")
    tags: List[str] = Field(default_factory=list, description="目标标签")
    progress: float = Field(..., description="目标完成进度，0.0-1.0")
    estimated_completion: Optional[datetime] = Field(None, description="预计完成时间")
    task_count: int = Field(..., description="关联任务数量")
    completed_task_count: int = Field(..., description="已完成任务数量")


class TaskSummary(BaseModel):
    """任务摘要信息"""
    id: str = Field(..., description="任务ID")
    title: str = Field(..., description="任务标题")
    status: StatusEnum = Field(..., description="任务状态")
    priority: PriorityEnum = Field(..., description="任务优先级")
    progress: float = Field(..., description="任务完成进度，0.0-1.0")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class TaskDetail(BaseModel):
    """任务详细信息"""
    id: str = Field(..., description="任务ID")
    objective_id: str = Field(..., description="所属目标ID")
    title: str = Field(..., description="任务标题")
    description: Optional[str] = Field(None, description="任务详细描述")
    status: StatusEnum = Field(..., description="任务状态")
    priority: PriorityEnum = Field(..., description="任务优先级")
    progress: float = Field(..., description="任务完成进度，0.0-1.0")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    started_at: Optional[datetime] = Field(None, description="开始执行时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    agent_type: str = Field(..., description="处理该任务的智能体类型")
    tags: List[str] = Field(default_factory=list, description="任务标签")
    dependencies: List[str] = Field(default_factory=list, description="依赖的任务ID列表")
    step_count: int = Field(..., description="步骤数量")
    completed_step_count: int = Field(..., description="已完成步骤数量")


class StepSummary(BaseModel):
    """步骤摘要信息"""
    id: str = Field(..., description="步骤ID")
    task_id: str = Field(..., description="所属任务ID")
    title: str = Field(..., description="步骤标题")
    status: StatusEnum = Field(..., description="步骤状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class StepDetail(BaseModel):
    """步骤详细信息"""
    id: str = Field(..., description="步骤ID")
    task_id: str = Field(..., description="所属任务ID")
    title: str = Field(..., description="步骤标题")
    description: Optional[str] = Field(None, description="步骤详细描述")
    status: StatusEnum = Field(..., description="步骤状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    started_at: Optional[datetime] = Field(None, description="开始执行时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    agent_type: str = Field(..., description="处理该步骤的智能体类型")
    input_data: Optional[Dict[str, Any]] = Field(None, description="步骤输入数据")
    output_data: Optional[Dict[str, Any]] = Field(None, description="步骤输出数据")
    error: Optional[str] = Field(None, description="错误信息")


class StepResult(BaseModel):
    """步骤执行结果"""
    step_id: str = Field(..., description="步骤ID")
    status: StatusEnum = Field(..., description="步骤状态")
    data: Dict[str, Any] = Field(..., description="结果数据")
    created_at: datetime = Field(..., description="创建时间")
    execution_time: float = Field(..., description="执行时间（秒）")


class WorkflowState(BaseModel):
    """工作流状态"""
    workflow_id: str = Field(..., description="工作流ID")
    objective_id: str = Field(..., description="关联目标ID")
    status: StatusEnum = Field(..., description="工作流状态")
    current_node: str = Field(..., description="当前节点名称")
    next_node: Optional[str] = Field(None, description="下一个节点名称")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    checkpoint_count: int = Field(..., description="检查点数量")
    execution_history: List[Dict[str, Any]] = Field(default_factory=list, description="执行历史")


class CheckpointSummary(BaseModel):
    """检查点摘要"""
    id: str = Field(..., description="检查点ID")
    workflow_id: str = Field(..., description="工作流ID")
    created_at: datetime = Field(..., description="创建时间")
    node: str = Field(..., description="创建检查点的节点名称")
    description: str = Field(..., description="检查点描述")


class SchedulerStatus(BaseModel):
    """调度器状态"""
    active: bool = Field(..., description="调度器是否活跃")
    worker_count: int = Field(..., description="工作线程数量")
    busy_workers: int = Field(..., description="忙碌工作线程数量")
    queue_size: int = Field(..., description="队列大小")
    processed_count: int = Field(..., description="已处理任务数量")
    failed_count: int = Field(..., description="失败任务数量")


class ResourceUsage(BaseModel):
    """资源使用情况"""
    cpu_percent: float = Field(..., description="CPU使用率")
    memory_percent: float = Field(..., description="内存使用率")
    disk_percent: float = Field(..., description="磁盘使用率")
    network_sent: int = Field(..., description="网络发送字节数")
    network_received: int = Field(..., description="网络接收字节数")


class ScheduleResponse(BaseModel):
    """调度响应"""
    schedule_ids: List[str] = Field(..., description="调度ID列表")
    status: str = Field(..., description="调度状态")


class OperationResponse(BaseModel):
    """操作响应"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="操作消息")
    data: Optional[Dict[str, Any]] = Field(None, description="操作返回数据")


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str = Field(..., description="错误详情")
    error_code: Optional[str] = Field(None, description="错误代码")
    timestamp: datetime = Field(default_factory=datetime.now, description="错误时间")


class MultiAgentStreamRequest(BaseModel):    """多智能体流式请求模型"""    query: str = Field(..., description="用户查询/研究问题")    thread_id: str = Field("__default__", description="会话ID，默认创建新会话")    locale: str = Field("zh-CN", description="语言设置，默认中文")    max_steps: int = Field(10, description="最大步骤数")    auto_execute: bool = Field(False, description="是否自动执行（无需人工确认）")    interrupt_feedback: Optional[str] = Field(None, description="中断反馈")    additional_context: Optional[Dict[str, Any]] = Field(None, description="额外上下文信息，用于提供更多背景")        @validator('query')    def query_must_not_be_empty(cls, v):        if not v or not v.strip():            raise ValueError('查询不能为空')        return v  