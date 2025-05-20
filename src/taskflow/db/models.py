# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow数据库模型模块。

定义系统使用的数据模型，包括研究目标、任务和步骤等。
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship

from src.taskflow.db.base import Base


class Objective(Base):
    """研究目标模型"""
    
    __tablename__ = "objectives"
    
    # 基本字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    query = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="CREATED", index=True)
    priority = Column(Integer, nullable=False, default=0, index=True)
    
    # 用户相关
    user_id = Column(String(100), nullable=True, index=True)
    
    # 元数据
    meta_data = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    completed_at = Column(DateTime, nullable=True)
    
    # 关系
    tasks = relationship("Task", back_populates="objective", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Objective(id={self.id}, title={self.title}, status={self.status})>"


class Task(Base):
    """任务模型"""
    
    __tablename__ = "tasks"
    
    # 基本字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    task_type = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="CREATED", index=True)
    priority = Column(Integer, nullable=False, default=0, index=True)
    
    # 关系字段
    objective_id = Column(String(36), ForeignKey("objectives.id"), nullable=False, index=True)
    parent_task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    
    # 依赖关系
    depends_on = Column(JSON, nullable=True)
    
    # 元数据
    meta_data = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    completed_at = Column(DateTime, nullable=True)
    
    # 关系
    objective = relationship("Objective", back_populates="tasks")
    parent_task = relationship("Task", remote_side=[id], backref="subtasks")
    steps = relationship("Step", back_populates="task", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title={self.title}, status={self.status})>"


class Step(Base):
    """步骤模型"""
    
    __tablename__ = "steps"
    
    # 基本字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    step_type = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="CREATED", index=True)
    priority = Column(Integer, nullable=False, default=0, index=True)
    
    # 执行信息
    agent_type = Column(String(100), nullable=True)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # 关系字段
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # 关系
    task = relationship("Task", back_populates="steps")
    
    def __repr__(self) -> str:
        return f"<Step(id={self.id}, name={self.name}, status={self.status})>"


class Workflow(Base):
    """工作流实例模型"""
    
    __tablename__ = "workflows"
    
    # 基本字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    workflow_type = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="CREATED", index=True)
    
    # 关系字段
    objective_id = Column(String(36), ForeignKey("objectives.id"), nullable=True, index=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    
    # 执行状态
    state = Column(JSON, nullable=True)
    current_node = Column(String(100), nullable=True)
    is_paused = Column(Boolean, default=False)
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # 关系
    checkpoints = relationship("WorkflowCheckpoint", back_populates="workflow", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Workflow(id={self.id}, name={self.name}, status={self.status})>"


class WorkflowCheckpoint(Base):
    """工作流检查点模型"""
    
    __tablename__ = "workflow_checkpoints"
    
    # 基本字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    node_name = Column(String(100), nullable=False)
    
    # 状态数据
    state = Column(JSON, nullable=False)
    
    # 关系字段
    workflow_id = Column(String(36), ForeignKey("workflows.id"), nullable=False, index=True)
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.now, index=True)
    
    # 关系
    workflow = relationship("Workflow", back_populates="checkpoints")
    
    def __repr__(self) -> str:
        return f"<WorkflowCheckpoint(id={self.id}, name={self.name}, workflow_id={self.workflow_id})>"


class IndustryStandard(Base):
    """行业标准模型"""
    
    __tablename__ = "industry_standards"
    
    # 基本字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    standard_name = Column(String(255), nullable=False, index=True)
    standard_code = Column(String(100), nullable=False, index=True, unique=True)
    industry_type = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # 发布信息
    issuing_authority = Column(String(255), nullable=False, index=True)
    effective_date = Column(DateTime, nullable=True)
    expiration_date = Column(DateTime, nullable=True)
    
    # 地区和分类
    regions = Column(JSON, nullable=False)  # 存储地区列表
    categories = Column(JSON, nullable=False)  # 存储标准分类
    
    # 详细内容
    meta_data = Column(JSON, nullable=True)  # 存储其他元数据
    
    # 时间字段
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self) -> str:
        return f"<IndustryStandard(id={self.id}, name={self.standard_name}, code={self.standard_code})>" 