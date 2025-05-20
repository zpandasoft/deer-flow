# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow工作流图模块。

基于LangGraph实现的工作流引擎，包含图构建和执行组件。
"""

from src.taskflow.graph.types import (
    TaskState, ObjectiveState, TaskItemState, StepState, MessageState,
    ResourceState, WorkflowMetadata, ObjectiveStatus, TaskStatus,
    StepStatus, QualityLevel, ResourceType, TaskType
)

from src.taskflow.graph.builder import (
    TaskflowGraphBuilder, build_research_workflow,
    build_analysis_workflow, build_task_executor_workflow,
    create_workflow_for_objective
)

from src.taskflow.graph.routers import (
    route_by_query_type, route_by_task_status, route_by_step_result,
    route_by_quality_eval, route_on_error, route_by_dependencies,
    route_by_objective_status, route_to_next_task, determine_initial_node
)

from src.taskflow.graph.nodes import (
    context_analyzer_node, objective_decomposer_node, task_analyzer_node,
    research_node, processing_node, quality_evaluator_node,
    synthesis_node, error_handler_node, select_next_task_node,
    initialize_workflow_node
)

__all__ = [
    # 类型
    "TaskState", "ObjectiveState", "TaskItemState", "StepState", "MessageState",
    "ResourceState", "WorkflowMetadata", "ObjectiveStatus", "TaskStatus",
    "StepStatus", "QualityLevel", "ResourceType", "TaskType",
    
    # 构建器
    "TaskflowGraphBuilder", "build_research_workflow",
    "build_analysis_workflow", "build_task_executor_workflow",
    "create_workflow_for_objective",
    
    # 路由器
    "route_by_query_type", "route_by_task_status", "route_by_step_result",
    "route_by_quality_eval", "route_on_error", "route_by_dependencies",
    "route_by_objective_status", "route_to_next_task", "determine_initial_node",
    
    # 节点
    "context_analyzer_node", "objective_decomposer_node", "task_analyzer_node",
    "research_node", "processing_node", "quality_evaluator_node",
    "synthesis_node", "error_handler_node", "select_next_task_node",
    "initialize_workflow_node"
] 