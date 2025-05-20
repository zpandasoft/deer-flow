# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
工作流节点函数模块。

定义工作流图中各节点的处理逻辑。
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, TypeVar, Union, cast

from src.taskflow.agents.base import BaseAgent
from src.taskflow.agents.context_analyzer import ContextAnalyzerAgent
from src.taskflow.agents.objective_decomposer import (
    ObjectiveDecomposerAgent, ObjectiveDecomposerInput, ObjectiveDecomposerOutput
)
from src.taskflow.agents.task_analyzer import TaskAnalyzerAgent
from src.taskflow.agents.research_agent import ResearchAgent
from src.taskflow.agents.step_planner import StepPlannerAgent
from src.taskflow.agents.factory import get_agent_by_name
from src.taskflow.exceptions import AgentError, WorkflowStateError
from src.taskflow.graph.types import (
    ObjectiveState, ObjectiveStatus, TaskState, TaskStatus, TaskItemState,
    StepState, StepStatus, TaskType, QualityLevel
)
from src.taskflow.prompts import apply_prompt_template


# 获取日志记录器
logger = logging.getLogger(__name__)


async def context_analyzer_node(state: TaskState) -> TaskState:
    """
    上下文分析节点。
    
    分析查询和上下文，确定研究领域和关键概念。
    
    Args:
        state: 工作流状态
        
    Returns:
        更新后的工作流状态
    """
    logger.info(f"执行上下文分析节点，目标ID: {state.objective.objective_id}")
    
    try:
        # 获取上下文分析智能体
        agent = cast(ContextAnalyzerAgent, get_agent_by_name("context_analyzer"))
        
        # 更新目标状态
        state.objective.status = ObjectiveStatus.ANALYZING
        
        # 记录节点访问
        state.mark_node_visited("context_analyzer")
        
        # 使用模板系统生成提示词
        messages = apply_prompt_template("context_analyzer", {
            "objective": {
                "query": state.objective.query,
                "objective_id": state.objective.objective_id,
            },
            "intermediate_data": {
                "language": state.intermediate_data.get("language", "zh"),
                "available_knowledge": "",
            },
            "metadata": state.objective.metadata
        })
        
        # 提取系统提示词和用户消息
        system_prompt = messages[0]["content"]
        
        # 更新智能体的系统提示词
        if agent.system_prompt != system_prompt:
            agent.system_prompt = system_prompt
        
        # 设置智能体输入
        agent_input = {
            "query": state.objective.query,
            "objective_id": state.objective.objective_id,
            "language": state.intermediate_data.get("language", "zh"),
            "metadata": state.objective.metadata
        }
        
        # 执行智能体
        result = await agent.run(agent_input)
        
        # 更新状态
        state.intermediate_data["context_analysis"] = result
        state.add_message(
            f"上下文分析完成。识别到研究领域: {result.get('domain', {}).get('primary', '未知')}，"
            f"关键概念: {', '.join(result.get('domain', {}).get('key_concepts', ['未知']))}",
            role="system"
        )
        
        return state
        
    except Exception as e:
        error_msg = f"上下文分析失败: {str(e)}"
        logger.error(error_msg)
        state.set_error("ContextAnalysisError", error_msg)
        raise WorkflowStateError(error_msg) from e


async def objective_decomposer_node(state: TaskState) -> TaskState:
    """
    目标分解节点。
    
    将复杂研究目标分解为子目标和具体任务。
    
    Args:
        state: 工作流状态
        
    Returns:
        更新后的工作流状态
    """
    logger.info(f"执行目标分解节点，目标ID: {state.objective.objective_id}")
    
    try:
        # 获取目标分解智能体
        agent = cast(ObjectiveDecomposerAgent, get_agent_by_name("objective_decomposer"))
        
        # 更新目标状态
        state.objective.status = ObjectiveStatus.DECOMPOSING
        
        # 记录节点访问
        state.mark_node_visited("objective_decomposer")
        
        # 准备上下文信息
        context_analysis = state.intermediate_data.get("context_analysis", {})
        
        # 设置智能体输入
        agent_input = ObjectiveDecomposerInput(
            objective_id=state.objective.objective_id,
            objective_title=state.objective.title,
            objective_description=state.objective.description,
            objective_query=state.objective.query,
            context=context_analysis
        )
        
        # 执行智能体
        result = await agent.run(agent_input)
        
        # 更新状态
        for i, task_data in enumerate(result.tasks):
            # 创建任务ID
            task_id = f"task-{state.objective.objective_id}-{i+1}"
            
            # 创建任务
            task = TaskItemState(
                task_id=task_id,
                objective_id=state.objective.objective_id,
                title=task_data.title,
                description=task_data.description,
                task_type=TaskType(task_data.task_type),
                priority=task_data.priority,
                status=TaskStatus.PENDING,
                metadata=task_data.metadata or {}
            )
            
            # 添加任务依赖关系（需要稍后处理）
            if task_data.depends_on:
                state.intermediate_data.setdefault("task_dependencies", {})[task_id] = task_data.depends_on
            
            # 添加任务到目标
            state.add_task(task)
        
        # 处理依赖关系
        if "task_dependencies" in state.intermediate_data:
            dependencies = state.intermediate_data["task_dependencies"]
            
            # 构建任务标题到ID的映射
            title_to_id = {task.title: task.task_id for task in state.objective.tasks}
            
            # 更新依赖关系
            for task_id, deps in dependencies.items():
                task = state.get_task_by_id(task_id)
                if task:
                    for dep_title in deps:
                        if dep_title in title_to_id:
                            dep_id = title_to_id[dep_title]
                            if dep_id != task_id:  # 避免自我依赖
                                task.depends_on.append(dep_id)
                                
                                # 更新被依赖任务的dependents列表
                                dep_task = state.get_task_by_id(dep_id)
                                if dep_task:
                                    dep_task.dependents.append(task_id)
        
        # 找出没有依赖的任务，将其状态设置为READY
        for task in state.objective.tasks:
            if not task.depends_on:
                task.status = TaskStatus.READY
        
        # 添加消息
        state.add_message(
            f"目标分解完成。识别到{len(state.objective.tasks)}个任务。",
            role="system"
        )
        
        return state
        
    except Exception as e:
        error_msg = f"目标分解失败: {str(e)}"
        logger.error(error_msg)
        state.set_error("ObjectiveDecompositionError", error_msg)
        raise WorkflowStateError(error_msg) from e


async def task_analyzer_node(state: TaskState) -> TaskState:
    """
    任务分析节点。
    
    分析任务要求和复杂度，确定任务类型。
    
    Args:
        state: 工作流状态
        
    Returns:
        更新后的工作流状态
    """
    logger.info("执行任务分析节点")
    
    try:
        # 获取任务分析智能体
        agent = cast(TaskAnalyzerAgent, get_agent_by_name("task_analyzer"))
        
        # 更新目标状态
        state.objective.status = ObjectiveStatus.PLANNING
        
        # 记录节点访问
        state.mark_node_visited("task_analyzer")
        
        # 获取当前任务
        current_task = state.current_task
        if not current_task:
            # 找一个READY状态的任务
            ready_tasks = [t for t in state.objective.tasks if t.status == TaskStatus.READY]
            if ready_tasks:
                # 按优先级排序
                ready_tasks.sort(key=lambda t: t.priority, reverse=True)
                current_task = ready_tasks[0]
                state.current_task = current_task
            else:
                raise WorkflowStateError("没有就绪的任务可供分析")
        
        # 设置智能体输入
        agent_input = {
            "task_id": current_task.task_id,
            "task_title": current_task.title,
            "task_description": current_task.description,
            "task_type": current_task.task_type,
            "objective": {
                "id": state.objective.objective_id,
                "title": state.objective.title,
                "query": state.objective.query
            },
            "context_analysis": state.intermediate_data.get("context_analysis", {})
        }
        
        # 执行智能体
        result = await agent.run(agent_input)
        
        # 更新状态
        current_task.metadata["analysis"] = result
        
        # 创建步骤
        for i, step_data in enumerate(result.get("steps", [])):
            step_id = f"step-{current_task.task_id}-{i+1}"
            
            step = StepState(
                step_id=step_id,
                task_id=current_task.task_id,
                title=step_data.get("title", f"步骤 {i+1}"),
                description=step_data.get("description", ""),
                status=StepStatus.PENDING,
                agent_name=step_data.get("agent_name"),
                metadata=step_data.get("metadata", {})
            )
            
            # 添加步骤到任务
            state.add_step_to_task(current_task.task_id, step)
        
        # 如果任务有步骤，并且状态是READY，则更新为RUNNING
        if current_task.steps and current_task.status == TaskStatus.READY:
            current_task.status = TaskStatus.RUNNING
            current_task.started_at = datetime.now()
            
            # 设置第一个步骤为就绪状态
            if current_task.steps:
                current_task.steps[0].status = StepStatus.READY
                state.current_step = current_task.steps[0]
        
        # 添加消息
        state.add_message(
            f"任务分析完成。任务'{current_task.title}'被分解为{len(current_task.steps)}个步骤。",
            role="system"
        )
        
        return state
        
    except Exception as e:
        error_msg = f"任务分析失败: {str(e)}"
        logger.error(error_msg)
        state.set_error("TaskAnalysisError", error_msg)
        raise WorkflowStateError(error_msg) from e


async def research_node(state: TaskState) -> TaskState:
    """
    研究节点。
    
    执行信息收集和研究任务。
    
    Args:
        state: 工作流状态
        
    Returns:
        更新后的工作流状态
    """
    logger.info("执行研究节点")
    
    try:
        # 获取研究智能体
        agent = cast(ResearchAgent, get_agent_by_name("research"))
        
        # 记录节点访问
        state.mark_node_visited("research")
        
        # 获取当前步骤
        current_step = state.current_step
        if not current_step:
            raise WorkflowStateError("没有当前步骤可执行")
        
        # 更新步骤状态
        current_step.status = StepStatus.RUNNING
        current_step.started_at = datetime.now()
        
        # 获取当前任务
        current_task = state.current_task
        if not current_task:
            raise WorkflowStateError("没有当前任务可执行")
        
        # 设置智能体输入
        agent_input = {
            "step_id": current_step.step_id,
            "step_title": current_step.title,
            "step_description": current_step.description,
            "task": {
                "id": current_task.task_id,
                "title": current_task.title,
                "description": current_task.description,
                "type": current_task.task_type,
            },
            "objective": {
                "id": state.objective.objective_id,
                "title": state.objective.title,
                "query": state.objective.query
            },
            "context_analysis": state.intermediate_data.get("context_analysis", {}),
            "previous_steps": [
                {
                    "id": step.step_id,
                    "title": step.title,
                    "result": step.output_data
                }
                for step in current_task.steps
                if step.step_id != current_step.step_id 
                and step.status == StepStatus.COMPLETED
            ]
        }
        
        # 执行智能体
        result = await agent.run(agent_input)
        
        # 更新步骤状态
        current_step.output_data = result
        current_step.status = StepStatus.COMPLETED
        current_step.completed_at = datetime.now()
        
        # 添加消息
        state.add_message(
            f"步骤'{current_step.title}'研究完成",
            role="system"
        )
        
        # 检查是否所有步骤都已完成
        all_steps_completed = all(
            step.status == StepStatus.COMPLETED
            for step in current_task.steps
        )
        
        if all_steps_completed:
            # 更新任务状态
            current_task.status = TaskStatus.COMPLETED
            current_task.completed_at = datetime.now()
            current_task.result_summary = "任务所有步骤已完成"
            
            # 检查依赖此任务的其他任务，更新它们的状态
            for dep_id in current_task.dependents:
                dep_task = state.get_task_by_id(dep_id)
                if dep_task:
                    # 检查依赖任务是否都已完成
                    all_deps_completed = all(
                        state.get_task_by_id(dep).status == TaskStatus.COMPLETED
                        for dep in dep_task.depends_on
                        if state.get_task_by_id(dep)
                    )
                    
                    if all_deps_completed and dep_task.status == TaskStatus.PENDING:
                        dep_task.status = TaskStatus.READY
            
            # 将current_task和current_step设为None
            state.current_task = None
            state.current_step = None
        else:
            # 找到下一个待执行的步骤
            next_pending_step = next(
                (step for step in current_task.steps 
                 if step.status == StepStatus.PENDING),
                None
            )
            
            if next_pending_step:
                next_pending_step.status = StepStatus.READY
                state.current_step = next_pending_step
        
        return state
        
    except Exception as e:
        error_msg = f"研究步骤执行失败: {str(e)}"
        logger.error(error_msg)
        
        # 更新步骤状态
        if state.current_step:
            state.current_step.status = StepStatus.FAILED
            state.current_step.error_message = str(e)
        
        state.set_error("ResearchError", error_msg)
        raise WorkflowStateError(error_msg) from e


async def processing_node(state: TaskState) -> TaskState:
    """
    处理节点。
    
    处理和转换数据。
    
    Args:
        state: 工作流状态
        
    Returns:
        更新后的工作流状态
    """
    logger.info("执行处理节点")
    
    try:
        # 记录节点访问
        state.mark_node_visited("processing")
        
        # 获取当前步骤
        current_step = state.current_step
        if not current_step:
            raise WorkflowStateError("没有当前步骤可执行")
        
        # 获取当前任务
        current_task = state.current_task
        if not current_task:
            raise WorkflowStateError("没有当前任务可执行")
        
        # 根据步骤指定的智能体名称获取对应智能体
        agent_name = current_step.agent_name or "processing"
        agent = get_agent_by_name(agent_name)
        
        # 更新步骤状态
        current_step.status = StepStatus.RUNNING
        current_step.started_at = datetime.now()
        
        # 设置智能体输入
        agent_input = {
            "step_id": current_step.step_id,
            "step_title": current_step.title,
            "step_description": current_step.description,
            "task": {
                "id": current_task.task_id,
                "title": current_task.title,
                "description": current_task.description,
                "type": current_task.task_type,
            },
            "objective": {
                "id": state.objective.objective_id,
                "title": state.objective.title,
                "query": state.objective.query
            },
            "context_analysis": state.intermediate_data.get("context_analysis", {}),
            "previous_steps": [
                {
                    "id": step.step_id,
                    "title": step.title,
                    "result": step.output_data
                }
                for step in current_task.steps
                if step.step_id != current_step.step_id 
                and step.status == StepStatus.COMPLETED
            ],
            "input_data": current_step.input_data or {}
        }
        
        # 执行智能体
        result = await agent.run(agent_input)
        
        # 更新步骤状态
        current_step.output_data = result
        current_step.status = StepStatus.COMPLETED
        current_step.completed_at = datetime.now()
        
        # 添加消息
        state.add_message(
            f"步骤'{current_step.title}'处理完成",
            role="system"
        )
        
        # 检查是否所有步骤都已完成
        all_steps_completed = all(
            step.status == StepStatus.COMPLETED
            for step in current_task.steps
        )
        
        if all_steps_completed:
            # 更新任务状态
            current_task.status = TaskStatus.COMPLETED
            current_task.completed_at = datetime.now()
            current_task.result_summary = "任务所有步骤已完成"
            
            # 检查依赖此任务的其他任务，更新它们的状态
            for dep_id in current_task.dependents:
                dep_task = state.get_task_by_id(dep_id)
                if dep_task:
                    # 检查依赖任务是否都已完成
                    all_deps_completed = all(
                        state.get_task_by_id(dep).status == TaskStatus.COMPLETED
                        for dep in dep_task.depends_on
                        if state.get_task_by_id(dep)
                    )
                    
                    if all_deps_completed and dep_task.status == TaskStatus.PENDING:
                        dep_task.status = TaskStatus.READY
            
            # 将current_task和current_step设为None
            state.current_task = None
            state.current_step = None
        else:
            # 找到下一个待执行的步骤
            next_pending_step = next(
                (step for step in current_task.steps 
                 if step.status == StepStatus.PENDING),
                None
            )
            
            if next_pending_step:
                next_pending_step.status = StepStatus.READY
                state.current_step = next_pending_step
        
        return state
        
    except Exception as e:
        error_msg = f"处理步骤执行失败: {str(e)}"
        logger.error(error_msg)
        
        # 更新步骤状态
        if state.current_step:
            state.current_step.status = StepStatus.FAILED
            state.current_step.error_message = str(e)
        
        state.set_error("ProcessingError", error_msg)
        raise WorkflowStateError(error_msg) from e


async def quality_evaluator_node(state: TaskState) -> TaskState:
    """
    质量评估节点。
    
    评估任务或步骤的执行质量。
    
    Args:
        state: 工作流状态
        
    Returns:
        更新后的工作流状态
    """
    logger.info("执行质量评估节点")
    
    try:
        # 记录节点访问
        state.mark_node_visited("quality_evaluator")
        
        # 获取评估目标（当前步骤或任务）
        target = state.current_step or state.current_task
        if not target:
            raise WorkflowStateError("没有可评估的目标")
        
        # 获取质量评估智能体
        agent = get_agent_by_name("quality_evaluator")
        
        # 设置智能体输入
        agent_input = {
            "target_id": getattr(target, "step_id", None) or getattr(target, "task_id", None),
            "target_type": "step" if hasattr(target, "step_id") else "task",
            "target_title": target.title,
            "target_description": target.description,
            "output_data": getattr(target, "output_data", None),
            "result_summary": getattr(target, "result_summary", None),
            "objective": {
                "id": state.objective.objective_id,
                "title": state.objective.title,
                "query": state.objective.query
            }
        }
        
        # 执行智能体
        result = await agent.run(agent_input)
        
        # 更新目标质量评估
        quality_level = result.get("quality_level", "ACCEPTABLE")
        target.quality_assessment = QualityLevel(quality_level)
        
        # 更新元数据
        target.metadata["quality_evaluation"] = {
            "score": result.get("score"),
            "feedback": result.get("feedback"),
            "improvement_suggestions": result.get("improvement_suggestions"),
            "evaluated_at": datetime.now().isoformat()
        }
        
        # 添加消息
        state.add_message(
            f"质量评估完成。评估等级: {quality_level}, "
            f"得分: {result.get('score')}, "
            f"反馈: {result.get('feedback')}",
            role="system"
        )
        
        return state
        
    except Exception as e:
        error_msg = f"质量评估失败: {str(e)}"
        logger.error(error_msg)
        state.set_error("QualityEvaluationError", error_msg)
        raise WorkflowStateError(error_msg) from e


async def synthesis_node(state: TaskState) -> TaskState:
    """
    合成节点。
    
    汇总多任务结果，生成综合报告。
    
    Args:
        state: 工作流状态
        
    Returns:
        更新后的工作流状态
    """
    logger.info("执行合成节点")
    
    try:
        # 记录节点访问
        state.mark_node_visited("synthesis")
        
        # 获取合成智能体
        agent = get_agent_by_name("synthesis")
        
        # 更新目标状态
        state.objective.status = ObjectiveStatus.SYNTHESIZING
        
        # 收集所有已完成任务的结果
        completed_tasks = [
            {
                "task_id": task.task_id,
                "title": task.title,
                "description": task.description,
                "task_type": str(task.task_type),
                "result_summary": task.result_summary,
                "steps": [
                    {
                        "step_id": step.step_id,
                        "title": step.title,
                        "output_data": step.output_data
                    }
                    for step in task.steps
                    if step.status == StepStatus.COMPLETED
                ]
            }
            for task in state.objective.tasks
            if task.status == TaskStatus.COMPLETED
        ]
        
        # 设置智能体输入
        agent_input = {
            "objective_id": state.objective.objective_id,
            "objective_title": state.objective.title,
            "objective_query": state.objective.query,
            "completed_tasks": completed_tasks,
            "context_analysis": state.intermediate_data.get("context_analysis", {})
        }
        
        # 执行智能体
        result = await agent.run(agent_input)
        
        # 更新目标状态
        state.objective.result_summary = result.get("summary")
        state.objective.status = ObjectiveStatus.COMPLETED
        state.objective.completed_at = datetime.now()
        
        # 更新中间数据
        state.intermediate_data["synthesis_result"] = result
        
        # 添加消息
        state.add_message(
            f"目标合成完成。生成了综合报告。",
            role="system"
        )
        
        return state
        
    except Exception as e:
        error_msg = f"结果合成失败: {str(e)}"
        logger.error(error_msg)
        state.set_error("SynthesisError", error_msg)
        raise WorkflowStateError(error_msg) from e


async def error_handler_node(state: TaskState) -> TaskState:
    """
    错误处理节点。
    
    处理执行过程中的异常情况。
    
    Args:
        state: 工作流状态
        
    Returns:
        更新后的工作流状态
    """
    logger.info("执行错误处理节点")
    
    try:
        # 记录节点访问
        state.mark_node_visited("error_handler")
        
        # 获取错误处理智能体
        agent = get_agent_by_name("error_handler")
        
        # 获取错误信息
        error = state.error
        if not error:
            logger.warning("没有错误信息需要处理")
            return state
        
        # 设置智能体输入
        agent_input = {
            "error_type": error.get("type"),
            "error_message": error.get("message"),
            "error_details": error.get("details", {}),
            "node_history": list(state.visited_nodes),
            "current_task": state.current_task.task_id if state.current_task else None,
            "current_step": state.current_step.step_id if state.current_step else None,
            "objective_id": state.objective.objective_id,
            "objective_status": str(state.objective.status)
        }
        
        # 执行智能体
        result = await agent.run(agent_input)
        
        # 处理错误恢复建议
        recovery_action = result.get("recovery_action")
        
        if recovery_action == "retry_step" and state.current_step:
            # 重试当前步骤
            state.current_step.retry_count += 1
            state.current_step.status = StepStatus.READY
            state.current_step.error_message = None
            
            # 更新消息
            state.add_message(
                f"错误处理：重试步骤 '{state.current_step.title}'",
                role="system"
            )
            
        elif recovery_action == "skip_step" and state.current_step and state.current_task:
            # 跳过当前步骤
            state.current_step.status = StepStatus.SKIPPED
            
            # 找到下一个步骤
            current_task = state.current_task
            next_step = None
            
            for i, step in enumerate(current_task.steps):
                if step.step_id == state.current_step.step_id and i + 1 < len(current_task.steps):
                    next_step = current_task.steps[i + 1]
                    break
            
            if next_step:
                next_step.status = StepStatus.READY
                state.current_step = next_step
                
                # 更新消息
                state.add_message(
                    f"错误处理：跳过步骤 '{state.current_step.title}'，继续下一步",
                    role="system"
                )
            else:
                # 没有更多步骤，完成任务
                current_task.status = TaskStatus.COMPLETED
                current_task.completed_at = datetime.now()
                state.current_step = None
                state.current_task = None
                
                # 更新消息
                state.add_message(
                    f"错误处理：跳过最后步骤，任务标记为完成",
                    role="system"
                )
                
        elif recovery_action == "fail_task" and state.current_task:
            # 标记当前任务为失败
            state.current_task.status = TaskStatus.FAILED
            state.current_task.error_message = error.get("message")
            state.current_step = None
            state.current_task = None
            
            # 更新消息
            state.add_message(
                f"错误处理：任务标记为失败",
                role="system"
            )
            
        elif recovery_action == "restart_workflow":
            # 重置工作流状态
            state.objective.status = ObjectiveStatus.CREATED
            state.current_task = None
            state.current_step = None
            state.visited_nodes.clear()
            
            # 更新消息
            state.add_message(
                f"错误处理：重置工作流，准备重新开始",
                role="system"
            )
            
        else:
            # 未知恢复行动或不需要操作
            state.add_message(
                f"错误处理：无法恢复错误，或不需要操作",
                role="system"
            )
        
        # 清除错误状态
        state.clear_error()
        
        # 更新恢复建议到中间数据
        state.intermediate_data.setdefault("error_history", []).append({
            "timestamp": datetime.now().isoformat(),
            "error": error,
            "recovery": result
        })
        
        return state
        
    except Exception as e:
        error_msg = f"错误处理失败: {str(e)}"
        logger.error(error_msg)
        
        # 更新错误状态
        state.set_error("ErrorHandlingError", error_msg)
        
        # 目标失败
        state.objective.status = ObjectiveStatus.FAILED
        state.objective.error_message = f"无法恢复的错误: {error_msg}"
        
        raise WorkflowStateError(error_msg) from e


async def select_next_task_node(state: TaskState) -> TaskState:
    """
    选择下一个任务节点。
    
    在当前任务完成后，选择下一个要执行的任务。
    
    Args:
        state: 工作流状态
        
    Returns:
        更新后的工作流状态
    """
    logger.info("执行选择下一个任务节点")
    
    try:
        # 记录节点访问
        state.mark_node_visited("select_next_task")
        
        # 如果当前任务仍在进行中，不执行选择
        if state.current_task and state.current_task.status == TaskStatus.RUNNING:
            return state
        
        # 找出所有就绪的任务
        ready_tasks = [
            task for task in state.objective.tasks
            if task.status == TaskStatus.READY
        ]
        
        if not ready_tasks:
            # 检查是否所有任务都已完成
            all_completed = all(
                task.status == TaskStatus.COMPLETED
                for task in state.objective.tasks
            )
            
            if all_completed:
                # 所有任务完成，可以进入合成阶段
                state.objective.status = ObjectiveStatus.SYNTHESIZING
                state.add_message("所有任务已完成，准备合成结果", role="system")
            else:
                # 有些任务未完成但没有就绪任务，可能是依赖关系问题
                state.add_message("没有就绪的任务可供执行", role="system")
                
            return state
        
        # 按优先级排序
        ready_tasks.sort(key=lambda t: t.priority, reverse=True)
        
        # 选择优先级最高的任务
        next_task = ready_tasks[0]
        state.current_task = next_task
        state.current_step = None
        
        # 更新消息
        state.add_message(
            f"选择任务 '{next_task.title}' 作为下一个要执行的任务",
            role="system"
        )
        
        return state
        
    except Exception as e:
        error_msg = f"选择下一个任务失败: {str(e)}"
        logger.error(error_msg)
        state.set_error("TaskSelectionError", error_msg)
        raise WorkflowStateError(error_msg) from e


async def initialize_workflow_node(state: TaskState) -> TaskState:
    """
    工作流初始化节点。
    
    初始化工作流状态。
    
    Args:
        state: 工作流状态
        
    Returns:
        更新后的工作流状态
    """
    logger.info("执行工作流初始化节点")
    
    try:
        # 记录节点访问
        state.mark_node_visited("initialize_workflow")
        
        # 添加初始消息
        state.add_message(
            f"工作流初始化。目标: {state.objective.title}, ID: {state.objective.objective_id}",
            role="system"
        )
        
        # 确保目标状态为CREATED
        state.objective.status = ObjectiveStatus.CREATED
        
        # 如果目标的started_at未设置，则设置
        if not state.objective.started_at:
            state.objective.started_at = datetime.now()
        
        return state
        
    except Exception as e:
        error_msg = f"工作流初始化失败: {str(e)}"
        logger.error(error_msg)
        state.set_error("WorkflowInitializationError", error_msg)
        raise WorkflowStateError(error_msg) from e 