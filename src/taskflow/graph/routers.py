# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
工作流条件路由函数模块。

定义工作流分支决策函数。
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Set, TypeVar, Union

from src.taskflow.exceptions import WorkflowStateError
from src.taskflow.graph.types import (
    ObjectiveStatus, QualityLevel, StepStatus, TaskState, TaskStatus, TaskType
)

# 获取日志记录器
logger = logging.getLogger(__name__)

# 定义路由结果类型
QueryRouteResult = Literal["research", "analysis", "development", "other"]
TaskRouteResult = Literal["ready", "running", "completed", "failed", "blocked"]
StepRouteResult = Literal["success", "retry", "fail", "next"]
QualityRouteResult = Literal["pass", "improve", "fail"]
ErrorRouteResult = Literal["retry", "fallback", "abort"]


def route_by_query_type(state: TaskState) -> QueryRouteResult:
    """
    根据查询类型路由。
    
    Args:
        state: 工作流状态
        
    Returns:
        路由结果
    """
    try:
        query = state.objective.query.lower()
        
        # 分析查询类型
        if any(kw in query for kw in ["研究", "调查", "分析", "评估", "比较"]):
            return "research"
        elif any(kw in query for kw in ["如何", "怎样", "方法", "步骤", "流程"]):
            return "analysis"
        elif any(kw in query for kw in ["开发", "构建", "创建", "编写", "设计"]):
            return "development"
        else:
            return "other"
    except Exception as e:
        logger.error(f"查询类型路由失败: {str(e)}")
        # 默认路由
        return "research"


def route_by_task_status(state: TaskState) -> TaskRouteResult:
    """
    根据任务状态路由。
    
    Args:
        state: 工作流状态
        
    Returns:
        路由结果
    """
    current_task = state.current_task
    
    if not current_task:
        logger.warning("缺少当前任务，无法确定路由")
        return "blocked"
        
    status = current_task.status
    
    # 根据状态决定下一步
    if status == TaskStatus.READY:
        return "ready"
    elif status == TaskStatus.RUNNING:
        return "running"
    elif status == TaskStatus.COMPLETED:
        return "completed"
    elif status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
        return "failed"
    else:
        # PENDING, PAUSED, BLOCKED等其他状态
        return "blocked"


def route_by_step_result(state: TaskState) -> StepRouteResult:
    """
    根据步骤结果路由。
    
    Args:
        state: 工作流状态
        
    Returns:
        路由结果
    """
    current_step = state.current_step
    
    if not current_step:
        logger.warning("缺少当前步骤，无法确定路由")
        return "next"
        
    # 检查步骤状态
    if current_step.status == StepStatus.COMPLETED:
        return "success"
    elif current_step.status == StepStatus.FAILED:
        # 检查是否可以重试
        if current_step.retry_count < current_step.max_retries:
            return "retry"
        else:
            return "fail"
    else:
        # 其他状态，继续下一步
        return "next"


def route_by_quality_eval(state: TaskState) -> QualityRouteResult:
    """
    根据质量评估结果路由。
    
    Args:
        state: 工作流状态
        
    Returns:
        路由结果
    """
    # 获取当前步骤或任务
    target = state.current_step or state.current_task
    
    if not target:
        logger.warning("缺少评估目标，无法确定路由")
        return "fail"
        
    quality = getattr(target, "quality_assessment", None)
    
    if not quality:
        logger.warning("目标未进行质量评估")
        return "pass"  # 默认通过
        
    # 根据质量等级决定路由
    if quality in (QualityLevel.EXCELLENT, QualityLevel.GOOD):
        return "pass"
    elif quality == QualityLevel.ACCEPTABLE:
        # 可接受但可能需要改进
        return "pass"  # 也可以设置为"improve"
    else:
        # NEEDS_IMPROVEMENT 或 POOR
        return "improve" if quality == QualityLevel.NEEDS_IMPROVEMENT else "fail"


def route_on_error(state: TaskState) -> ErrorRouteResult:
    """
    错误处理路由。
    
    Args:
        state: 工作流状态
        
    Returns:
        路由结果
    """
    if not state.error:
        logger.warning("无错误信息，不需要错误处理")
        return "retry"  # 默认尝试重试
        
    error_type = state.error.get("type", "")
    
    # 根据错误类型决定处理方式
    if error_type in ("TemporaryError", "ResourceError", "TimeoutError"):
        return "retry"  # 临时错误，尝试重试
    elif error_type in ("InputError", "ValidationError", "ConfigError"):
        return "fallback"  # 输入或配置错误，尝试备选方案
    else:
        # 其他严重错误
        return "abort"


def route_by_dependencies(state: TaskState) -> Literal["proceed", "wait", "skip"]:
    """
    根据任务依赖关系路由。
    
    Args:
        state: 工作流状态
        
    Returns:
        路由结果
    """
    current_task = state.current_task
    
    if not current_task:
        logger.warning("缺少当前任务，无法检查依赖")
        return "proceed"
        
    # 如果没有依赖，直接执行
    if not current_task.depends_on:
        return "proceed"
        
    # 检查所有依赖的任务是否完成
    for dep_task_id in current_task.depends_on:
        dep_task = state.get_task_by_id(dep_task_id)
        
        if not dep_task:
            logger.warning(f"依赖的任务 {dep_task_id} 不存在")
            return "skip"  # 依赖不存在，可能需要跳过当前任务
            
        if dep_task.status != TaskStatus.COMPLETED:
            # 依赖任务未完成
            logger.info(f"等待依赖任务 {dep_task_id} 完成")
            return "wait"
            
    # 所有依赖都已完成
    return "proceed"


def route_by_objective_status(state: TaskState) -> Literal["continue", "complete", "error"]:
    """
    根据目标状态路由。
    
    Args:
        state: 工作流状态
        
    Returns:
        路由结果
    """
    status = state.objective.status
    
    if status in (ObjectiveStatus.FAILED, ObjectiveStatus.CANCELLED):
        return "error"
    elif status == ObjectiveStatus.COMPLETED:
        return "complete"
    else:
        # 其他状态都表示正在进行中
        return "continue"


def route_to_next_task(state: TaskState) -> str:
    """
    路由到下一个应该执行的任务。
    
    Args:
        state: 工作流状态
        
    Returns:
        下一个任务ID，如果没有下一个任务则返回"end"
    """
    # 找出所有未完成且就绪的任务
    ready_tasks = [
        task for task in state.objective.tasks
        if task.status == TaskStatus.READY
    ]
    
    # 按优先级排序
    ready_tasks.sort(key=lambda t: t.priority, reverse=True)
    
    # 检查依赖关系
    for task in ready_tasks:
        # 确保所有依赖任务都已完成
        all_deps_completed = True
        
        for dep_id in task.depends_on:
            dep_task = state.get_task_by_id(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                all_deps_completed = False
                break
                
        if all_deps_completed:
            return task.task_id
            
    # 如果没有就绪任务，检查是否所有任务都已完成
    all_completed = all(
        task.status == TaskStatus.COMPLETED
        for task in state.objective.tasks
    )
    
    if all_completed:
        return "end"
        
    # 如果有任务处于PENDING状态但依赖未满足，则等待
    return "wait"


def determine_initial_node(state: TaskState) -> str:
    """
    确定工作流的初始节点。
    
    Args:
        state: 工作流状态
        
    Returns:
        初始节点名称
    """
    # 获取目标状态
    status = state.objective.status
    
    # 根据状态决定初始节点
    if status == ObjectiveStatus.CREATED:
        return "context_analyzer"
    elif status == ObjectiveStatus.ANALYZING:
        return "objective_decomposer"
    elif status == ObjectiveStatus.DECOMPOSING:
        return "task_analyzer"
    elif status == ObjectiveStatus.PLANNING:
        return "research"
    elif status == ObjectiveStatus.EXECUTING:
        # 检查当前任务和步骤
        if state.current_task and state.current_task.task_type == TaskType.RESEARCH:
            return "research"
        elif state.current_task and state.current_task.task_type == TaskType.ANALYSIS:
            return "processing"
        else:
            return "task_analyzer"  # 重新分析任务
    else:
        # 对于其他状态，重新开始
        return "context_analyzer" 