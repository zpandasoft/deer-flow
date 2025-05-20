# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
工作流图构建器模块。

提供构建工作流图的接口和工具。
"""

import logging
import uuid
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, Type, Union, Callable

from langgraph.graph import StateGraph, START, END

from src.taskflow.exceptions import WorkflowStateError
from src.taskflow.graph.types import (
    TaskState, ObjectiveStatus, TaskType, TaskStatus, StepStatus
)
from src.taskflow.graph.routers import (
    route_by_query_type, route_by_task_status, route_by_step_result,
    route_by_quality_eval, route_on_error, route_by_dependencies,
    route_by_objective_status
)
from src.taskflow.graph.nodes import (
    context_analyzer_node, objective_decomposer_node, task_analyzer_node,
    research_node, processing_node, quality_evaluator_node,
    synthesis_node, error_handler_node, select_next_task_node,
    initialize_workflow_node
)


# 获取日志记录器
logger = logging.getLogger(__name__)


class TaskflowGraphBuilder:
    """工作流图构建器类"""
    
    def __init__(self, state_type: Type = TaskState):
        """
        初始化工作流图构建器。
        
        Args:
            state_type: 状态类型
        """
        self.graph = StateGraph(state_type)
        self.nodes = {}
        self.conditional_routers = {}
        self.edges = []
        self.conditional_edges = []
        self.state_type = state_type
        logger.info(f"初始化工作流图构建器，状态类型: {state_type.__name__}")
    
    def add_node(self, name: str, node_function: Callable) -> "TaskflowGraphBuilder":
        """
        添加工作流节点。
        
        Args:
            name: 节点名称
            node_function: 节点函数
            
        Returns:
            构建器实例
        """
        self.nodes[name] = node_function
        self.graph.add_node(name, node_function)
        logger.debug(f"添加节点: {name}")
        return self
    
    def add_edge(self, source: str, target: str) -> "TaskflowGraphBuilder":
        """
        添加工作流边。
        
        Args:
            source: 源节点名称
            target: 目标节点名称
            
        Returns:
            构建器实例
        """
        self.edges.append((source, target))
        self.graph.add_edge(source, target)
        logger.debug(f"添加边: {source} -> {target}")
        return self
    
    def add_conditional_edges(
        self, 
        source: str, 
        condition: Callable, 
        targets: Dict[str, str]
    ) -> "TaskflowGraphBuilder":
        """
        添加条件边。
        
        Args:
            source: 源节点名称
            condition: 条件函数
            targets: 条件值到目标节点的映射
            
        Returns:
            构建器实例
        """
        self.conditional_routers[source] = condition
        self.conditional_edges.append((source, condition, targets))
        self.graph.add_conditional_edges(source, condition, targets)
        logger.debug(f"添加条件边: {source} -> {condition.__name__} -> {targets}")
        return self
    
    def add_error_handler(self, handler_node: str = "error_handler") -> "TaskflowGraphBuilder":
        """
        为所有节点添加错误处理。
        
        Args:
            handler_node: 错误处理节点名称
            
        Returns:
            构建器实例
        """
        # 确保错误处理节点已添加
        if handler_node not in self.nodes:
            raise WorkflowStateError(f"错误处理节点未定义: {handler_node}")
        
        # 定义错误检测函数
        def has_error(state: TaskState) -> bool:
            return state.error is not None
        
        # 为每个节点添加错误处理边
        for node_name in self.nodes:
            if node_name != handler_node:
                # 添加条件边，如果有错误，跳转到错误处理节点
                self.graph.add_conditional_edges(
                    node_name,
                    has_error,
                    {
                        True: handler_node,
                        False: None  # 保持原有边的流向
                    }
                )
                logger.debug(f"为节点添加错误处理: {node_name} -> {handler_node}")
        
        return self
    
    def build(self) -> StateGraph:
        """
        构建工作流图。
        
        Returns:
            编译后的工作流图
        """
        # 验证图结构
        if not self.nodes:
            raise WorkflowStateError("图中没有添加任何节点")
        
        # 编译图
        compiled_graph = self.graph.compile()
        logger.info(f"工作流图构建完成，节点数: {len(self.nodes)}, 边数: {len(self.edges) + len(self.conditional_edges)}")
        return compiled_graph


def build_research_workflow() -> StateGraph:
    """
    构建研究工作流。
    
    专注于信息收集和研究分析的工作流。
    
    Returns:
        研究工作流图
    """
    builder = TaskflowGraphBuilder()
    
    # 添加节点
    builder.add_node("initialize", initialize_workflow_node)
    builder.add_node("context_analyzer", context_analyzer_node)
    builder.add_node("objective_decomposer", objective_decomposer_node)
    builder.add_node("task_analyzer", task_analyzer_node)
    builder.add_node("research", research_node)
    builder.add_node("quality_evaluator", quality_evaluator_node)
    builder.add_node("select_next_task", select_next_task_node)
    builder.add_node("synthesis", synthesis_node)
    builder.add_node("error_handler", error_handler_node)
    
    # 添加基本流程边
    builder.add_edge(START, "initialize")
    builder.add_edge("initialize", "context_analyzer")
    builder.add_edge("context_analyzer", "objective_decomposer")
    builder.add_edge("objective_decomposer", "task_analyzer")
    
    # 根据任务类型路由到不同节点
    builder.add_conditional_edges(
        "task_analyzer",
        lambda state: str(state.current_task.task_type) if state.current_task else "UNKNOWN",
        {
            str(TaskType.RESEARCH): "research",
            str(TaskType.ANALYSIS): "research",
            "UNKNOWN": "select_next_task"
        }
    )
    
    # 研究步骤完成后进行质量评估
    builder.add_edge("research", "quality_evaluator")
    
    # 根据质量评估结果决定下一步
    builder.add_conditional_edges(
        "quality_evaluator",
        route_by_quality_eval,
        {
            "pass": "select_next_task",
            "improve": "research",  # 返回研究节点改进
            "fail": "task_analyzer"  # 重新分析任务
        }
    )
    
    # 选择下一个任务
    builder.add_conditional_edges(
        "select_next_task",
        lambda state: "end" if all(task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED) 
                                 for task in state.objective.tasks) else "task_analyzer",
        {
            "end": "synthesis",
            "task_analyzer": "task_analyzer"
        }
    )
    
    # 合成节点到结束
    builder.add_edge("synthesis", END)
    
    # 错误处理
    builder.add_conditional_edges(
        "error_handler",
        route_on_error,
        {
            "retry": "task_analyzer",
            "fallback": "select_next_task",
            "abort": END
        }
    )
    
    # 为所有节点添加错误处理
    builder.add_error_handler()
    
    return builder.build()


def build_analysis_workflow() -> StateGraph:
    """
    构建分析工作流。
    
    专注于数据处理和分析的工作流。
    
    Returns:
        分析工作流图
    """
    builder = TaskflowGraphBuilder()
    
    # 添加节点
    builder.add_node("initialize", initialize_workflow_node)
    builder.add_node("context_analyzer", context_analyzer_node)
    builder.add_node("objective_decomposer", objective_decomposer_node)
    builder.add_node("task_analyzer", task_analyzer_node)
    builder.add_node("processing", processing_node)
    builder.add_node("quality_evaluator", quality_evaluator_node)
    builder.add_node("select_next_task", select_next_task_node)
    builder.add_node("synthesis", synthesis_node)
    builder.add_node("error_handler", error_handler_node)
    
    # 添加基本流程边
    builder.add_edge(START, "initialize")
    builder.add_edge("initialize", "context_analyzer")
    builder.add_edge("context_analyzer", "objective_decomposer")
    builder.add_edge("objective_decomposer", "task_analyzer")
    
    # 根据任务类型路由到不同节点
    builder.add_conditional_edges(
        "task_analyzer",
        lambda state: str(state.current_task.task_type) if state.current_task else "UNKNOWN",
        {
            str(TaskType.ANALYSIS): "processing",
            str(TaskType.INTEGRATION): "processing",
            "UNKNOWN": "select_next_task"
        }
    )
    
    # 处理步骤完成后进行质量评估
    builder.add_edge("processing", "quality_evaluator")
    
    # 根据质量评估结果决定下一步
    builder.add_conditional_edges(
        "quality_evaluator",
        route_by_quality_eval,
        {
            "pass": "select_next_task",
            "improve": "processing",  # 返回处理节点改进
            "fail": "task_analyzer"  # 重新分析任务
        }
    )
    
    # 选择下一个任务
    builder.add_conditional_edges(
        "select_next_task",
        lambda state: "end" if all(task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED) 
                                 for task in state.objective.tasks) else "task_analyzer",
        {
            "end": "synthesis",
            "task_analyzer": "task_analyzer"
        }
    )
    
    # 合成节点到结束
    builder.add_edge("synthesis", END)
    
    # 错误处理
    builder.add_conditional_edges(
        "error_handler",
        route_on_error,
        {
            "retry": "task_analyzer",
            "fallback": "select_next_task",
            "abort": END
        }
    )
    
    # 为所有节点添加错误处理
    builder.add_error_handler()
    
    return builder.build()


def build_task_executor_workflow() -> StateGraph:
    """
    构建任务执行工作流。
    
    通用的任务执行工作流，能够适应多种任务类型。
    
    Returns:
        任务执行工作流图
    """
    builder = TaskflowGraphBuilder()
    
    # 添加节点
    builder.add_node("initialize", initialize_workflow_node)
    builder.add_node("context_analyzer", context_analyzer_node)
    builder.add_node("objective_decomposer", objective_decomposer_node)
    builder.add_node("task_analyzer", task_analyzer_node)
    builder.add_node("research", research_node)
    builder.add_node("processing", processing_node)
    builder.add_node("quality_evaluator", quality_evaluator_node)
    builder.add_node("select_next_task", select_next_task_node)
    builder.add_node("synthesis", synthesis_node)
    builder.add_node("error_handler", error_handler_node)
    
    # 添加基本流程边
    builder.add_edge(START, "initialize")
    builder.add_edge("initialize", "context_analyzer")
    builder.add_edge("context_analyzer", "objective_decomposer")
    builder.add_edge("objective_decomposer", "select_next_task")
    builder.add_edge("select_next_task", "task_analyzer")
    
    # 根据任务类型路由到不同节点
    builder.add_conditional_edges(
        "task_analyzer",
        lambda state: str(state.current_task.task_type) if state.current_task else "UNKNOWN",
        {
            str(TaskType.RESEARCH): "research",
            str(TaskType.ANALYSIS): "processing",
            str(TaskType.DEVELOPMENT): "processing",
            str(TaskType.INTEGRATION): "processing",
            str(TaskType.TESTING): "research",
            str(TaskType.DOCUMENTATION): "processing",
            str(TaskType.EVALUATION): "processing",
            "UNKNOWN": "select_next_task"
        }
    )
    
    # 执行步骤完成后进行质量评估
    builder.add_edge("research", "quality_evaluator")
    builder.add_edge("processing", "quality_evaluator")
    
    # 根据质量评估结果决定下一步
    builder.add_conditional_edges(
        "quality_evaluator",
        route_by_quality_eval,
        {
            "pass": "select_next_task",
            "improve": lambda state: "research" if state.current_task and state.current_task.task_type in 
                                                (TaskType.RESEARCH, TaskType.TESTING) else "processing",
            "fail": "task_analyzer"  # 重新分析任务
        }
    )
    
    # 选择下一个任务的路由
    builder.add_conditional_edges(
        "select_next_task",
        route_by_objective_status,
        {
            "continue": "task_analyzer",
            "complete": "synthesis",
            "error": "error_handler"
        }
    )
    
    # 合成节点到结束
    builder.add_edge("synthesis", END)
    
    # 错误处理
    builder.add_conditional_edges(
        "error_handler",
        route_on_error,
        {
            "retry": "select_next_task",
            "fallback": "synthesis",
            "abort": END
        }
    )
    
    # 为所有节点添加错误处理
    builder.add_error_handler()
    
    return builder.build()


def create_workflow_for_objective(objective_query: str) -> Tuple[StateGraph, TaskState]:
    """
    根据目标查询创建适合的工作流和初始状态。
    
    Args:
        objective_query: 目标查询字符串
        
    Returns:
        工作流图和初始状态元组
    """
    # 分析查询类型
    query_lower = objective_query.lower()
    
    # 选择工作流类型
    if any(kw in query_lower for kw in ["研究", "调查", "分析", "评估", "比较"]):
        workflow = build_research_workflow()
        workflow_type = "research"
    elif any(kw in query_lower for kw in ["开发", "实现", "编写", "构建", "创建"]):
        workflow = build_task_executor_workflow()
        workflow_type = "executor"
    else:
        workflow = build_analysis_workflow()
        workflow_type = "analysis"
    
    # 创建目标ID
    objective_id = f"obj-{uuid.uuid4()}"
    
    # 确定目标标题
    title = objective_query
    if len(title) > 50:
        title = title[:47] + "..."
    
    # 创建初始状态
    from src.taskflow.graph.types import WorkflowMetadata, ObjectiveState
    
    workflow_metadata = WorkflowMetadata(
        workflow_id=f"wf-{uuid.uuid4()}",
        workflow_type=workflow_type,
        user_id=None,  # 可以在调用时设置
        tags=[]
    )
    
    objective = ObjectiveState(
        objective_id=objective_id,
        title=title,
        query=objective_query,
        status=ObjectiveStatus.CREATED
    )
    
    initial_state = TaskState(
        workflow_metadata=workflow_metadata,
        objective=objective
    )
    
    logger.info(f"为目标创建工作流，类型: {workflow_type}, 目标ID: {objective_id}")
    
    return workflow, initial_state 