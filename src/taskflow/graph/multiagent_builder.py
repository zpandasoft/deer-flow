# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
多智能体工作流图构建器。

基于LangGraph实现的多智能体协作工作流定义。
"""

from typing import Dict, List, Optional, Union, cast, Any
from uuid import uuid4

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from src.taskflow.graph.nodes import (
    context_analyzer_node, objective_decomposer_node, task_analyzer_node,
    research_node, processing_node, quality_evaluator_node,
    synthesis_node, error_handler_node
)
from src.taskflow.graph.types import TaskState, WorkflowMetadata, ObjectiveState


def build_multiagent_graph():
    """
    构建多智能体工作流图
    
    返回:
        StateGraph: 构建好的LangGraph工作流图
    """
    # 创建状态图
    workflow = StateGraph(TaskState)
     # 添加节点
    workflow.add_node("context_analyzer", context_analyzer_node)    
    workflow.add_node("objective_decomposer", objective_decomposer_node)    
    workflow.add_node("task_analyzer", task_analyzer_node)    
    workflow.add_node("research", research_node)    
    workflow.add_node("quality_evaluator", quality_evaluator_node)   
    workflow.add_node("processing", processing_node)    
    workflow.add_node("synthesis", synthesis_node)    
    workflow.add_node("error_handler", error_handler_node)       
    # 设置入口点和终止点 (LangGraph 0.4.x需要明确设置)    
    workflow.set_entry_point("context_analyzer")    
    # END作为终止点在添加边时已经隐含设置
    
    # 定义状态转换边
    workflow.add_edge("context_analyzer", "objective_decomposer")
    workflow.add_edge("objective_decomposer", "task_analyzer")
    workflow.add_edge("task_analyzer", "research")
    workflow.add_edge("research", "quality_evaluator")
    
    # 添加条件边
    workflow.add_conditional_edges(
        "quality_evaluator",
        evaluate_quality,
        {
            "complete": "processing",
            "incomplete": "research",
        }
    )
    
    workflow.add_edge("processing", "synthesis")
    workflow.add_edge("synthesis", END)
    
    # 添加错误处理路由 (适配LangGraph 0.4.x版本)
    # 注意: 在0.4.x版本中，不再使用set_error_handler方法
    # 而是通过当节点出错时调用error_handler_node来处理
    def handle_error(state, error):
        """当发生错误时被调用的处理函数"""
        updated_state = state.copy()
        updated_state["error"] = {
            "message": str(error),
            "node": state.get("current_node", "unknown"),
            "timestamp": str(uuid4())
        }
        updated_state["next_node"] = "error_handler"
        return updated_state
    
    # 编译工作流
    # 在LangGraph 0.4.x中，错误处理机制已更改
    # 此处简单编译，错误处理通过节点路由实现
    compiled_workflow = workflow.compile()
    
    return compiled_workflow


def evaluate_quality(state: Dict) -> str:
    """
    评估执行结果质量
    
    参数:
        state: 当前工作流状态
        
    返回:
        str: 评估结果，"complete"或"incomplete"
    """
    # 获取当前步骤ID和执行结果
    current_step = state.get("current_step", {})
    step_id = current_step.get("step_id")
    
    if not step_id:
        return "incomplete"
    
    result = state.get("execution_results", {}).get(step_id, {})
    
    # 检查质量评分
    quality_score = result.get("quality_score", 0)
    content_sufficient = state.get("content_sufficient", False)
    
    if quality_score >= 80 or content_sufficient:
        return "complete"
    else:
        return "incomplete"


def error_handler(state: Dict, error: Exception) -> Dict:
    """
    工作流错误处理器
    
    参数:
        state: 当前工作流状态
        error: 异常对象
        
    返回:
        Dict: 更新后的状态
    """
    # 记录错误
    updated_state = state.copy()
    updated_state["error"] = {
        "message": str(error),
        "node": state.get("current_node", "unknown"),
        "timestamp": str(uuid4())
    }
    
    # 设置下一个节点
    updated_state["next_node"] = "error_handler"
    
    return updated_state 