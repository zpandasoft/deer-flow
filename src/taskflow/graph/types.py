# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
工作流状态类型模块。

定义工作流中使用的各种状态类型。
"""

from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel, Field, root_validator

# 状态枚举定义
class ObjectiveStatus(str, Enum):
    """研究目标状态枚举"""
    CREATED = "CREATED"  # 已创建
    ANALYZING = "ANALYZING"  # 分析中
    DECOMPOSING = "DECOMPOSING"  # 分解中
    PLANNING = "PLANNING"  # 规划中
    EXECUTING = "EXECUTING"  # 执行中
    SYNTHESIZING = "SYNTHESIZING"  # 合成中
    COMPLETED = "COMPLETED"  # 已完成
    FAILED = "FAILED"  # 失败
    CANCELLED = "CANCELLED"  # 已取消
    PAUSED = "PAUSED"  # 已暂停


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "PENDING"  # 待处理
    READY = "READY"  # 就绪
    SCHEDULED = "SCHEDULED"  # 已调度
    RUNNING = "RUNNING"  # 运行中
    PAUSED = "PAUSED"  # 已暂停
    COMPLETED = "COMPLETED"  # 已完成
    FAILED = "FAILED"  # 失败
    CANCELLED = "CANCELLED"  # 已取消
    BLOCKED = "BLOCKED"  # 被阻塞


class StepStatus(str, Enum):
    """步骤状态枚举"""
    PENDING = "PENDING"  # 待处理
    READY = "READY"  # 就绪
    RUNNING = "RUNNING"  # 运行中
    PAUSED = "PAUSED"  # 已暂停
    COMPLETED = "COMPLETED"  # 已完成
    FAILED = "FAILED"  # 失败
    CANCELLED = "CANCELLED"  # 已取消
    SKIPPED = "SKIPPED"  # 已跳过


class QualityLevel(str, Enum):
    """质量评估等级枚举"""
    EXCELLENT = "EXCELLENT"  # 优秀
    GOOD = "GOOD"  # 良好
    ACCEPTABLE = "ACCEPTABLE"  # 可接受
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"  # 需要改进
    POOR = "POOR"  # 差


class ResourceType(str, Enum):
    """资源类型枚举"""
    LLM = "LLM"  # 大语言模型
    DATABASE = "DATABASE"  # 数据库
    WORKER = "WORKER"  # 工作线程
    API = "API"  # 外部API
    MEMORY = "MEMORY"  # 内存
    DISK = "DISK"  # 磁盘
    CUSTOM = "CUSTOM"  # 自定义


class TaskType(str, Enum):
    """任务类型枚举"""
    RESEARCH = "RESEARCH"  # 研究类型
    ANALYSIS = "ANALYSIS"  # 分析类型
    DEVELOPMENT = "DEVELOPMENT"  # 开发类型
    INTEGRATION = "INTEGRATION"  # 集成类型
    TESTING = "TESTING"  # 测试类型
    DOCUMENTATION = "DOCUMENTATION"  # 文档类型
    EVALUATION = "EVALUATION"  # 评估类型
    OTHER = "OTHER"  # 其他类型


# 基础模型定义
class BaseState(BaseModel):
    """工作流基础状态模型"""
    
    class Config:
        """Pydantic配置类"""
        extra = "allow"  # 允许额外字段
        arbitrary_types_allowed = True


class MessageState(BaseModel):
    """消息状态模型"""
    
    content: str = Field(..., description="消息内容")
    role: str = Field("system", description="消息角色")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    metadata: Optional[Dict[str, Any]] = Field(None, description="消息元数据")


class ResourceState(BaseModel):
    """资源状态模型"""
    
    resource_id: str = Field(..., description="资源ID")
    resource_type: ResourceType = Field(..., description="资源类型")
    status: str = Field("available", description="资源状态")
    allocated_at: Optional[datetime] = Field(None, description="分配时间")
    released_at: Optional[datetime] = Field(None, description="释放时间")
    metadata: Optional[Dict[str, Any]] = Field(None, description="资源元数据")


class StepState(BaseModel):
    """步骤状态模型"""
    
    step_id: str = Field(..., description="步骤ID")
    task_id: str = Field(..., description="所属任务ID")
    title: str = Field(..., description="步骤标题")
    description: Optional[str] = Field(None, description="步骤描述")
    status: StepStatus = Field(default=StepStatus.PENDING, description="步骤状态")
    agent_name: Optional[str] = Field(None, description="执行智能体名称")
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    output_data: Optional[Dict[str, Any]] = Field(None, description="输出数据")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    quality_assessment: Optional[QualityLevel] = Field(None, description="质量评估")
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=3, description="最大重试次数")
    resources: List[ResourceState] = Field(default_factory=list, description="使用的资源")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="步骤元数据")


class TaskItemState(BaseModel):
    """任务项状态模型"""
    
    task_id: str = Field(..., description="任务ID")
    objective_id: str = Field(..., description="所属目标ID")
    title: str = Field(..., description="任务标题")
    description: Optional[str] = Field(None, description="任务描述")
    task_type: TaskType = Field(..., description="任务类型")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    priority: int = Field(default=0, description="优先级（0-10）")
    steps: List[StepState] = Field(default_factory=list, description="步骤列表")
    depends_on: List[str] = Field(default_factory=list, description="依赖的任务ID列表")
    dependents: List[str] = Field(default_factory=list, description="依赖此任务的任务ID列表")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    result_summary: Optional[str] = Field(None, description="结果摘要")
    quality_assessment: Optional[QualityLevel] = Field(None, description="质量评估")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="任务元数据")


class ObjectiveState(BaseModel):
    """研究目标状态模型"""
    
    objective_id: str = Field(..., description="目标ID")
    title: str = Field(..., description="目标标题")
    description: Optional[str] = Field(None, description="目标描述")
    query: str = Field(..., description="原始查询")
    status: ObjectiveStatus = Field(default=ObjectiveStatus.CREATED, description="目标状态")
    tasks: List[TaskItemState] = Field(default_factory=list, description="任务列表")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    result_summary: Optional[str] = Field(None, description="结果摘要")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="目标元数据")
    

class WorkflowMetadata(BaseModel):
    """工作流元数据模型"""

    workflow_id: str = Field(..., description="工作流ID")
    workflow_type: str = Field(..., description="工作流类型")
    version: str = Field(default="1.0", description="工作流版本")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    checkpoint_ids: List[str] = Field(default_factory=list, description="检查点ID列表")
    is_paused: bool = Field(default=False, description="是否暂停")
    latest_node: Optional[str] = Field(None, description="最新执行的节点")
    transitions: List[Dict[str, Any]] = Field(default_factory=list, description="状态转换记录")
    user_id: Optional[str] = Field(None, description="用户ID")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    additional_data: Dict[str, Any] = Field(default_factory=dict, description="附加数据")


class TaskState(BaseState):
    """完整的工作流状态模型"""
    
    # 工作流元数据
    workflow_metadata: WorkflowMetadata = Field(..., description="工作流元数据")
    
    # 研究目标
    objective: ObjectiveState = Field(..., description="研究目标")
    
    # 当前正在处理的任务
    current_task: Optional[TaskItemState] = Field(None, description="当前任务")
    
    # 当前正在执行的步骤
    current_step: Optional[StepState] = Field(None, description="当前步骤")
    
    # 消息历史
    messages: List[MessageState] = Field(default_factory=list, description="消息历史")
    
    # 存储过程中的中间数据
    intermediate_data: Dict[str, Any] = Field(default_factory=dict, description="中间数据")
    
    # 错误信息
    error: Optional[Dict[str, Any]] = Field(None, description="错误信息")
    
    # 状态追踪
    visited_nodes: Set[str] = Field(default_factory=set, description="已访问的节点")
    
    # 资源跟踪
    allocated_resources: List[ResourceState] = Field(default_factory=list, description="已分配的资源")
    
    @root_validator(skip_on_failure=True)
    def check_task_consistency(cls, values):
        """验证任务一致性"""
        objective = values.get("objective")
        current_task = values.get("current_task")
        
        if objective and current_task:
            # 确保current_task是objective中的一个任务
            task_ids = {task.task_id for task in objective.tasks}
            if current_task.task_id not in task_ids:
                objective.tasks.append(current_task)
        
        return values
    
    def add_message(self, content: str, role: str = "system", metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        添加消息到历史记录。
        
        Args:
            content: 消息内容
            role: 消息角色
            metadata: 消息元数据
        """
        message = MessageState(
            content=content,
            role=role,
            created_at=datetime.now(),
            metadata=metadata or {}
        )
        self.messages.append(message)
    
    def set_error(self, error_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        设置错误信息。
        
        Args:
            error_type: 错误类型
            message: 错误消息
            details: 错误详情
        """
        self.error = {
            "type": error_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
    
    def clear_error(self) -> None:
        """清除错误信息"""
        self.error = None
    
    def mark_node_visited(self, node_name: str) -> None:
        """
        标记节点为已访问。
        
        Args:
            node_name: 节点名称
        """
        self.visited_nodes.add(node_name)
    
    def get_task_by_id(self, task_id: str) -> Optional[TaskItemState]:
        """
        通过ID获取任务。
        
        Args:
            task_id: 任务ID
            
        Returns:
            找到的任务，如果不存在则返回None
        """
        for task in self.objective.tasks:
            if task.task_id == task_id:
                return task
        return None
    
    def get_step_by_id(self, step_id: str) -> Optional[StepState]:
        """
        通过ID获取步骤。
        
        Args:
            step_id: 步骤ID
            
        Returns:
            找到的步骤，如果不存在则返回None
        """
        for task in self.objective.tasks:
            for step in task.steps:
                if step.step_id == step_id:
                    return step
        return None
    
    def add_task(self, task: TaskItemState) -> None:
        """
        添加任务到目标。
        
        Args:
            task: 任务实例
        """
        # 检查任务是否已存在
        existing = self.get_task_by_id(task.task_id)
        if existing is None:
            self.objective.tasks.append(task)
    
    def add_step_to_task(self, task_id: str, step: StepState) -> bool:
        """
        向任务添加步骤。
        
        Args:
            task_id: 任务ID
            step: 步骤实例
            
        Returns:
            是否成功添加
        """
        task = self.get_task_by_id(task_id)
        if task:
            # 检查步骤是否已存在
            if not any(s.step_id == step.step_id for s in task.steps):
                task.steps.append(step)
                return True
        return False
    
    def allocate_resource(self, resource: ResourceState) -> None:
        """
        分配资源。
        
        Args:
            resource: 资源实例
        """
        resource.allocated_at = datetime.now()
        self.allocated_resources.append(resource)
    
    def release_resource(self, resource_id: str) -> bool:
        """
        释放资源。
        
        Args:
            resource_id: 资源ID
            
        Returns:
            是否成功释放
        """
        for i, resource in enumerate(self.allocated_resources):
            if resource.resource_id == resource_id:
                resource.released_at = datetime.now()
                resource.status = "released"
                self.allocated_resources.pop(i)
                return True
        return False 