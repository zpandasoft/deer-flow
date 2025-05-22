# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

# 标准库导入
import json
import logging
import re
import traceback
from typing import Dict, List

# 第三方库导入
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

# 本地模块导入
from src.agents.agents import (
    context_analyzer_agent,
    objective_decomposer_agent,
    task_analyzer_agent,
    sufficiency_evaluator_agent,
    research_agent,
    processing_agent,
    quality_evaluator_agent,
    synthesis_agent,
    error_handler_agent,
    human_interaction_agent,
)
from src.agents.patch_context_analyzer import mock_context_analyzer_agent
from src.database import init_db_connection, get_db_service
from src.tools import web_search_tool
from .types import State
from langgraph.types import interrupt



# 初始化日志记录器
logger = logging.getLogger("graph.multiagent_builder")

# 初始化数据库连接
init_db_connection()


def _context_analyzer_node(state: State):
    """上下文分析节点"""
    try:
        # 添加当前节点名称到状态中，用于数据库记录
        state["current_node"] = "context_analyzer"
        # 添加显式调试日志
        logger.info("上下文分析节点开始执行，准备调用智能体")
        
        # 使用mock版本的context_analyzer_agent
        result = mock_context_analyzer_agent(state)
        
        # 日志记录结果
        logger.info(f"上下文分析完成，检查是否需要进行网络搜索")
        
        # 检查是否需要进行网络搜索
        need_web_search = False
        search_questions = []
        
        # 从消息中提取JSON内容
        if "messages" in result:
            for message in result["messages"]:
                if hasattr(message, "content") and message.content:
                    # 尝试从消息内容中提取JSON
                    json_match = re.search(r'```json\n(.+?)\n```', message.content, re.DOTALL)
                    if json_match:
                        try:
                            content_json = json.loads(json_match.group(1))
                            # 检查是否需要网络搜索
                            if "scenario" in content_json and content_json["scenario"].get("need_web_search", False):
                                need_web_search = True
                            
                            # 提取搜索问题
                            if "knowledge_sufficiency" in content_json and "search_questions" in content_json["knowledge_sufficiency"]:
                                search_questions = content_json["knowledge_sufficiency"]["search_questions"]
                        except json.JSONDecodeError as e:
                            logger.warning(f"无法解析消息中的JSON内容: {e}")
        
        # 如果需要网络搜索且有搜索问题
        if need_web_search and search_questions:
            logger.info(f"检测到需要网络搜索，共有{len(search_questions)}个搜索问题")
            search_results = []
            
            # 对每个搜索问题执行搜索
            for question in search_questions:
                query = question.get("question", "")
                if query:
                    logger.info(f"执行搜索: {query}")
                    try:
                        # 调用网络搜索工具
                        search_result = web_search_tool.invoke(query)
                        search_results.append({
                            "query": query,
                            "result": search_result
                        })
                        logger.info(f"搜索完成: {search_result}")
                    except Exception as e:
                        logger.error(f"搜索失败: {query}, 错误: {str(e)}")
            
            # 将搜索结果添加到状态中
            if search_results:
                result["search_results"] = search_results
                logger.info(f"已将{len(search_results)}个搜索结果添加到状态中")
        
        # 从数据库获取数据库服务实例
        db_service = get_db_service()
        
        # 保存上下文分析结果到数据库
        if "objective_id" in result and "context_analysis" in result:
            db_service.save_context_analysis_result(
                objective_id=result["objective_id"],
                llm_response=result["context_analysis"]
            )
        
        logger.info(f"上下文分析节点处理完成，下一步应该进入objective_decomposer节点")
        return result
    except Exception as e:
        error_msg = f"Context Analyzer Error:\nFile: {__file__}\nLine: {traceback.extract_tb(e.__traceback__)[-1].lineno}\nError: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        logger.error(error_msg)
        raise


 # 使用演示数据，避免重复调用大模型
objective_decomposer_result = {
    "research_question": "关于'光伏组件出口法国需要完成哪些合规目标'的最新信息是什么？",
    "decomposition_approach": "基于法规、技术标准和市场准入要求的维度，将出口合规问题分解为法律、技术和认证等层面的目标。",
    "objectives": [
        {
            "objective_id": "obj-001",
            "title": "识别并理解法国及欧盟相关法律法规",
            "description": "明确适用于光伏组件出口至法国的欧盟和法国本地法律法规，包括环境、贸易、产品安全等方面的法律要求。",
            "justification": "确保出口产品符合所有强制性法律条款，避免因违规导致的法律风险或罚款。",
            "evaluation_criteria": "列出完整的适用法律法规清单，并提供每项法规的核心要求摘要。",
            "priority": 1,
            "dependencies": [],
            "estimated_complexity": "高"
        },
        {
            "objective_id": "obj-002",
            "title": "获取并分析法国市场准入的技术标准",
            "description": "研究法国市场对光伏组件的技术规范，例如性能、电气安全、耐久性等要求，以及具体的测试方法和认证流程。",
            "justification": "技术标准是产品进入市场的基本门槛，未达标的产品将无法通过海关检查或获得销售许可。",
            "evaluation_criteria": "整理出一份完整的技术标准清单，并附带每项标准的具体实施指南或参考文档链接。",
            "priority": 2,
            "dependencies": ["obj-001"],
            "estimated_complexity": "中"
        }
    ],
    "coverage_analysis": "这些目标全面覆盖了光伏组件出口法国所需的法律、技术、认证、物流及政策动态等关键领域，能够有效支持企业实现合规出口。",
    "decomposition_rationale": "采用自上而下的系统化分解方法，从宏观法规到具体执行细节逐步展开，确保各目标既独立又互补，符合MECE原则。"
}


def _objective_decomposer_node(state: State):
    """目标分解节点"""
    # 添加当前节点名称到状态中，用于数据库记录
    state["current_node"] = "objective_decomposer"
    
    # 添加显式调试日志
    logger.info("目标分解节点开始执行，准备分解研究目标")
    
    # result = objective_decomposer_agent(state)
    result = objective_decomposer_result
    
    # 记录分解结果
    if "research_question" in result:
        logger.info(f"研究问题: {result['research_question']}")
    if "decomposition_approach" in result:
        logger.info(f"分解方法: {result['decomposition_approach']}")
    
    # 获取数据库服务实例
    db_service = get_db_service()
    
    # 保存目标分解结果到数据库
    if "objectives" in result:
        logger.info(f"目标分解结果: {result['objectives']}")
        objective_ids = db_service.save_objective_decomposer_result(result["objectives"])
        # 将目标ID添加到状态中以供后续节点使用
        if objective_ids and len(objective_ids) > 0:
            result["objective_id"] = objective_ids[0]
    
    return result


def _task_analyzer_node(state: State):
    """任务分析节点"""
    # 添加当前节点名称到状态中，用于数据库记录
    state["current_node"] = "task_analyzer"
    # objectives=state["objectives"]
    # 添加显式调试日志
    logger.info(f"任务分析节点开始执行，准备分析目标任务")
    
    # 记录当前要分析的目标
    if "objective_id" in state:
        logger.info(f"当前分析的目标ID: {state['objective_id']}")

    # 调用任务分析智能体
    result = task_analyzer_agent(state)
    
    # 获取数据库服务实例
    db_service = get_db_service()
    
    # 保存任务分析结果到数据库
    if "objective_id" in result and "tasks" in result:
        logger.info(f"任务分析结果: {result['tasks']}")
        task_results = db_service.save_task_analyzer_result(
            objective_id=result["objective_id"],
            llm_response=result["tasks"]
        )
        # 将任务ID和步骤ID添加到状态中以供后续节点使用
        if task_results:
            result["task_ids"] = task_results.get("task_ids", [])
            result["step_ids"] = task_results.get("step_ids", [])
    
    return result


def _sufficiency_evaluator_node(state: State):
    """充分性评估节点"""
    # 添加当前节点名称到状态中，用于数据库记录
    state["current_node"] = "sufficiency_evaluator"
    
    # 添加显式调试日志
    logger.info("充分性评估节点开始执行，准备评估任务充分性")
    
    # 获取循环计数器，如果不存在则初始化为0
    sufficiency_loop_count = state.get("sufficiency_loop_count", 0)
    # 设置最大循环次数，默认为1
    max_sufficiency_loops = state.get("max_sufficiency_loops", 1)
    
    # 增加循环计数
    sufficiency_loop_count += 1
    
    # 检查是否达到最大循环次数
    if sufficiency_loop_count > max_sufficiency_loops:
        # 如果达到最大循环次数，强制设置为充分
        # logger.warning(f"已达到充分性评估最大循环次数({max_sufficiency_loops})，强制设置为充分")
        
        # 从状态中获取任务列表，如果没有则创建一个空列表
        tasks = state.get("tasks", [])
        
        # 更新状态，强制设置为充分
        return {
            **state,
            "is_sufficient": True,
            "sufficiency_loop_count": sufficiency_loop_count,
            "pending_research_tasks": tasks,
            "completed_research_tasks": [],
            "current_task_index": 0,
            "forced_sufficient": True  # 标记为强制充分
        }
    
    # 调用充分性评估智能体
    result = sufficiency_evaluator_agent(state)
    
    # 记录评估结果
#     logger.info(f"充分性评估结果: {result}")
    
    # 如果评估为不充分，需要进行网络搜索补充信息
    if not result.get("is_sufficient", False):
        logger.info("评估结果不充分，准备进行网络搜索补充信息")
        search_questions = result.get("search_questions", [])
        
        if search_questions:
            search_results = []
            for question in search_questions:
                query = question.get("question", "")
                if query:
                    logger.info(f"执行搜索: {query}")
                    try:
                        # 调用网络搜索工具
                        search_result = web_search_tool.invoke(query)
                        search_results.append({
                            "query": query,
                            "result": search_result
                        })
                        logger.info(f"搜索完成: {search_result}")
                    except Exception as e:
                        logger.error(f"搜索失败: {query}, 错误: {str(e)}")
            
            # 将搜索结果添加到评估结果中
            if search_results:
                result["search_results"] = search_results
                logger.info(f"已将{len(search_results)}个搜索结果添加到评估结果中")
    
    # 如果评估为充分，准备并行研究任务
    if result.get("is_sufficient", False):
        # 从状态中获取任务列表
        tasks = result.get("tasks", [])
        
        # 更新状态
        return {
            **state,
            **result,
            "sufficiency_loop_count": sufficiency_loop_count,
            "pending_research_tasks": tasks,
            "completed_research_tasks": [],
            "current_task_index": 0
        }
    
    # 如果评估为不充分，返回结果并包含循环计数
    return {**state, **result, "sufficiency_loop_count": sufficiency_loop_count}


def _research_agent_node(state: State):
    """研究智能体节点，支持并行执行多个研究任务"""
    # 添加当前节点名称到状态中，用于数据库记录
    state["current_node"] = "research_agent"
    
    # 获取数据库服务实例
    db_service = get_db_service()
    
    # 获取循环计数器，如果不存在则初始化为0
    research_loop_count = state.get("research_loop_count", 0)
    # 设置最大循环次数，默认为1
    max_research_loops = state.get("max_research_loops", 1)
    
    # 增加循环计数
    research_loop_count += 1
    
    # 获取当前任务
    pending_tasks = state.get("pending_research_tasks", [])
    current_index = state.get("current_task_index", 0)
    
    # 如果没有更多任务，返回当前状态
    if not pending_tasks or current_index >= len(pending_tasks):
        return {
            **state, 
            "research_status": "completed",
            "research_loop_count": research_loop_count
        }
    
    # 检查是否达到最大循环次数
    if research_loop_count > max_research_loops:
        # 如果达到最大循环次数，强制完成所有任务
        logger.warning(f"已达到研究智能体最大循环次数({max_research_loops})，强制完成所有任务")
        
        # 将所有待处理任务标记为已完成，但结果为空
        completed_tasks = state.get("completed_research_tasks", [])
        for task in pending_tasks[current_index:]:
            completed_tasks.append({
                "task": task,
                "result": {"content": "由于达到最大循环次数限制，此任务被自动标记为完成"},
                "forced_complete": True  # 标记为强制完成
            })
        
        # 更新状态，强制设置为已完成所有任务
        return {
            **state,
            "research_status": "completed",
            "research_loop_count": research_loop_count,
            "completed_research_tasks": completed_tasks,
            "current_task_index": len(pending_tasks),
            "forced_complete": True  # 标记为强制完成
        }
    
    current_task = pending_tasks[current_index]
    
    # 检查是否是并行执行模式
    parallel_mode = state.get("parallel_execution", False)
    if parallel_mode:
        # 在并行模式下，我们会模拟多个任务同时执行
        # 实际实现中，可能需要使用异步机制或任务队列来实现真正的并行
        tasks_to_process = pending_tasks[current_index:min(current_index+3, len(pending_tasks))]
        completed_tasks = state.get("completed_research_tasks", [])
        
        for task in tasks_to_process:
            # 对每个任务调用研究智能体
            result = research_agent({
                **state, 
                "current_task": task,
                "task_id": task.get("id", f"task-{len(completed_tasks)}")
            })
            
            # 保存研究结果到数据库
            if "research_results" in result:
                db_service.save_research_result(
                    task_id=task.get("id", f"task-{len(completed_tasks)}"),
                    llm_response=result["research_results"]
                )
            
            # 保存结果
            completed_tasks.append({
                "task": task,
                "result": result.get("research_results", {})
            })
        
        # 更新状态
        return {
            **state,
            "completed_research_tasks": completed_tasks,
            "current_task_index": current_index + len(tasks_to_process),
            "research_loop_count": research_loop_count
        }
    else:
        # 单任务顺序执行模式
        # 调用研究智能体处理当前任务
        result = research_agent({
            **state, 
            "current_task": current_task,
            "task_id": current_task.get("id", f"task-{current_index}")
        })
        
        # 保存研究结果到数据库
        if "research_results" in result:
            db_service.save_research_result(
                task_id=current_task.get("id", f"task-{current_index}"),
                llm_response=result["research_results"]
            )
        
        # 更新完成的任务列表和当前任务索引
        completed_tasks = state.get("completed_research_tasks", [])
        completed_tasks.append({
            "task": current_task,
            "result": result.get("research_results", {})
        })
        
        # 更新状态
        return {
            **state,
            **result,
            "completed_research_tasks": completed_tasks,
            "current_task_index": current_index + 1,
            "research_loop_count": research_loop_count
        }


def _process_research_results(state: State):
    """处理所有研究结果，支持并行任务的结果整合"""
    # 添加当前节点名称到状态中，用于数据库记录
    state["current_node"] = "processing_agent"
    
    # 添加显式调试日志
    logger.info("处理节点开始执行，准备整合研究结果")
    
    # 获取数据库服务实例
    db_service = get_db_service()
    
    # 收集所有已完成的研究任务结果
    completed_tasks = state.get("completed_research_tasks", [])
    
    if not completed_tasks:
        return {**state, "processing_complete": True}
    
    # 按照任务类别或主题对结果进行分组
    # 这里我们简化处理，实际可能需要更复杂的结果分类和整合
    categorized_results = {}
    for task in completed_tasks:
        category = task["task"].get("category", "general")
        if category not in categorized_results:
            categorized_results[category] = []
        categorized_results[category].append(task["result"])
    
    # 对每个类别的结果进行处理
    processed_results = {}
    for category, results in categorized_results.items():
        # 调用处理智能体处理每个类别的研究结果
        category_result = processing_agent({
            **state, 
            "category": category,
            "research_results": results
        })
        
        # 保存处理结果到数据库
        if "processing_results" in category_result:
            db_service.save_processing_result(
                category=category,
                llm_response=category_result["processing_results"]
            )
        
        processed_results[category] = category_result.get("processing_results", {})
    
    # 整合所有处理结果
    return {
        **state,
        "all_processed_results": processed_results,
        "processing_complete": True
    }


def _quality_evaluator_node(state: State):
    """质量评估节点 - 对应流程图中的完成度评估智能体"""
    # 添加当前节点名称到状态中，用于数据库记录
    state["current_node"] = "quality_evaluator"
    
    # 添加显式调试日志
    logger.info("质量评估节点开始执行，准备评估研究结果质量")
    
    # 获取数据库服务实例
    db_service = get_db_service()
    
    # 获取当前评估的研究任务
    current_task_index = state.get("current_task_index", 0) - 1  # 获取刚刚完成的任务索引
    completed_tasks = state.get("completed_research_tasks", [])
    
    # 如果没有完成的任务，返回当前状态
    if not completed_tasks or current_task_index < 0:
        return {**state, "quality_passed": True}
    
    # 获取最近完成的任务及其结果
    current_task = completed_tasks[current_task_index]
    
    # 调用质量评估智能体评估研究结果
    evaluation_result = quality_evaluator_agent({
        **state, 
        "evaluation_task": current_task["task"],
        "evaluation_result": current_task["result"]
    })
    
    # 保存质量评估结果到数据库
    if "evaluation_result" in evaluation_result:
        db_service.save_quality_evaluation_result(
            task_id=current_task["task"].get("id"),
            llm_response=evaluation_result["evaluation_result"],
            quality_passed=evaluation_result.get("quality_passed", False)
        )
    
    # 如果质量评估不通过，标记该任务需要重新研究
    if not evaluation_result.get("quality_passed", True):
        # 将任务重新添加到待处理队列，并调整当前索引
        pending_tasks = state.get("pending_research_tasks", [])
        pending_tasks.append(current_task["task"])
        
        # 从已完成任务中移除该任务
        completed_tasks.pop(current_task_index)
        
        return {
            **state,
            **evaluation_result,
            "pending_research_tasks": pending_tasks,
            "completed_research_tasks": completed_tasks,
            "quality_passed": False
        }
    
    # 如果所有研究任务都已完成且质量评估通过
    if current_task_index == len(completed_tasks) - 1 and len(completed_tasks) == len(state.get("pending_research_tasks", [])):
        return {
            **state,
            **evaluation_result,
            "quality_passed": True,
            "all_research_complete": True
        }
    
    # 如果只是当前任务质量评估通过，继续下一个任务
    return {
        **state,
        **evaluation_result,
        "quality_passed": True
    }


def _synthesis_agent_node(state: State):
    """合成智能体节点"""
    # 添加当前节点名称到状态中，用于数据库记录
    state["current_node"] = "synthesis_agent"
    
    # 获取数据库服务实例
    db_service = get_db_service()

    # 调用合成智能体
    result = synthesis_agent(state)
    
    # 保存合成结果到数据库
    if "synthesis_result" in result:
        db_service.save_synthesis_result(
            llm_response=result["synthesis_result"]
        )
    
    return result


def _error_handler_node(state: State):
    """错误处理节点，负责处理工作流执行过程中的错误和异常"""
    # 添加当前节点名称到状态中，用于数据库记录
    state["current_node"] = "error_handler"
    
    # 获取数据库服务实例
    db_service = get_db_service()
    
    # 获取错误信息
    error = state.get("error", {})
    error_type = error.get("type", "unknown")
    error_message = error.get("message", "未知错误")
    error_source = error.get("source", "unknown")
    
    # 保存错误信息到数据库
    db_service.save_error_log(
        error_type=error_type,
        error_message=error_message,
        error_source=error_source,
        traceback=error.get("traceback", "")
    )
    
    # 记录错误
    logger.error(f"错误发生: {error_type} - {error_message} 来源: {error_source}")
    
    # 根据错误类型和来源处理错误
    if error_type == "task_execution":
        # 任务执行错误处理
        affected_task = error.get("task", {})
        # 尝试重置任务状态并重新执行
        pending_tasks = state.get("pending_research_tasks", [])
        if affected_task:
            pending_tasks.append(affected_task)
        
        # 生成错误恢复策略
        recovery_plan = error_handler_agent({
            "error": error,
            "state": state
        })
        
        # 应用恢复策略
        return {
            **state,
            "error": None,  # 清除错误状态
            "pending_research_tasks": pending_tasks,
            "recovery_plan": recovery_plan.get("recovery_plan", {}),
            "recovery_action": "retry_task"
        }
    
    elif error_type == "data_processing":
        # 数据处理错误处理
        # 尝试恢复或使用备用处理方法
        recovery_plan = error_handler_agent({
            "error": error,
            "state": state
        })
        
        return {
            **state,
            "error": None,
            "processing_method": recovery_plan.get("alternative_method", "backup"),
            "recovery_action": "retry_processing"
        }
    
    elif error_type == "user_interaction":
        # 用户交互错误处理
        # 通知用户并重试或提供替代选项
        return {
            **state,
            "error": None,
            "needs_human_interaction": True,
            "interaction_message": f"交互过程中出现问题: {error_message}，请提供进一步指示。",
            "recovery_action": "request_user_guidance"
        }
    
    else:
        # 一般错误处理
        # 尝试恢复到最后一个稳定状态
        recovery_plan = error_handler_agent({
            "error": error,
            "state": state
        })
        
        return {
            **state,
            "error": None,
            "recovery_plan": recovery_plan.get("recovery_plan", {}),
            "recovery_action": "restart_from_checkpoint",
            "checkpoint": state.get("last_stable_checkpoint", {})
        }


def _determine_error_recovery_path(state: State) -> str:
    """根据错误恢复策略决定下一步节点"""
    recovery_action = state.get("recovery_action", "")
    
    if recovery_action == "retry_task":
        return "research_agent"
    elif recovery_action == "retry_processing":
        return "processing_agent"
    elif recovery_action == "request_user_guidance":
        return "human_interaction"
    elif recovery_action == "restart_from_checkpoint":
        return "context_analyzer"  # 默认从头开始
    else:
        return "context_analyzer"  # 默认从头开始


def _wrap_node_with_error_handling(node_func):
    """包装节点函数，添加错误处理功能"""
    def wrapped_node(state):
        try:
            # 保存当前状态作为检查点
            checkpoint = {
                "messages": state.get("messages", []),
                "completed_research_tasks": state.get("completed_research_tasks", []),
                "pending_research_tasks": state.get("pending_research_tasks", []),
                "current_task_index": state.get("current_task_index", 0)
            }
            
            # 执行原始节点函数
            result = node_func(state)
            
            # 添加检查点信息
            if isinstance(result, dict):
                result["last_stable_checkpoint"] = checkpoint
            
            return result
        except Exception as e:
            # 捕获异常，生成错误状态
            import traceback
            error_info = {
                "type": "node_execution",
                "message": str(e),
                "traceback": traceback.format_exc(),
                "source": node_func.__name__
            }
            
            # 返回包含错误信息的状态
            return {
                **state,
                "error": error_info,
                "last_stable_checkpoint": checkpoint
            }
    
    return wrapped_node


def _human_interaction_node(state: State):
    """人机交互节点"""
    # 添加当前节点名称到状态中，用于数据库记录
    state["current_node"] = "human_interaction"
    # 调用人机交互智能体
    return human_interaction_agent(state)


def _user_feedback_node(state: State):
    """用户反馈节点，处理用户对最终结果的反馈"""
    # 添加当前节点名称到状态中，用于数据库记录
    state["current_node"] = "user_feedback"
    
   
    
    # 向用户展示最终报告
    final_report = state.get("final_report", "")
    if final_report:
        feedback = interrupt(f"以下是最终报告，请提供反馈:\n\n{final_report}")
        
        # 处理用户反馈
        if feedback:
            return {
                **state,
                "user_feedback": {
                    "type": "question" if "?" in feedback else "comment",
                    "content": feedback
                }
            }
    
    # 如果没有反馈或没有最终报告，返回当前状态
    return state


def _handle_user_feedback(state: State):
    """处理用户反馈"""
    # 添加当前节点名称到状态中，用于数据库记录
    state["current_node"] = "handle_feedback"
    
    # 获取用户反馈
    user_feedback = state.get("user_feedback", {})
    feedback_type = user_feedback.get("type", "")
    
    # 根据反馈类型更新状态
    if feedback_type == "question":
        # 用户提出了追加问题，重新启动流程
        return {
            **state,
            "needs_reanalysis": True,
            "additional_question": user_feedback.get("content", ""),
            "previous_results": state.get("completed_research_tasks", [])
        }
    elif feedback_type == "modification":
        # 用户要求修改某项结果
        target_task_id = user_feedback.get("target_task_id")
        if target_task_id:
            # 找到需要修改的任务
            completed_tasks = state.get("completed_research_tasks", [])
            pending_tasks = state.get("pending_research_tasks", [])
            
            # 寻找目标任务
            target_task = None
            target_index = -1
            for i, task in enumerate(completed_tasks):
                if task["task"].get("id") == target_task_id:
                    target_task = task["task"]
                    target_index = i
                    break
            
            if target_task and target_index >= 0:
                # 将任务添加回待处理队列
                pending_tasks.append({
                    **target_task,
                    "modification_request": user_feedback.get("content", "")
                })
                # 从已完成任务中移除
                completed_tasks.pop(target_index)
                
                return {
                    **state,
                    "pending_research_tasks": pending_tasks,
                    "completed_research_tasks": completed_tasks,
                    "needs_reexecution": True
                }
    
    # 默认情况：继续流程
    return state


def _evaluate_sufficiency(state: State) -> str:
    """评估任务设计是否充分"""
    if state.get("is_sufficient", False):
        return "sufficient"
    else:
        return "insufficient"


def _evaluate_research_status(state: State) -> str:
    """评估研究状态"""
    pending_tasks = state.get("pending_research_tasks", [])
    current_index = state.get("current_task_index", 0)
    
    # 如果还有研究任务需要执行
    if pending_tasks and current_index < len(pending_tasks):
        return "in_progress"
    
    # 如果所有研究任务已完成
    if pending_tasks and current_index >= len(pending_tasks):
        return "completed"
    
    # 如果没有待处理的任务
    return "no_tasks"


def _evaluate_quality(state: State) -> str:
    """评估质量是否合格"""
    if state.get("quality_passed", False):
        return "passed"
    else:
        return "failed"


def _evaluate_user_feedback(state: State) -> str:
    """评估用户反馈，决定下一步"""
    user_feedback = state.get("user_feedback", {})
    feedback_type = user_feedback.get("type", "")
    
    if feedback_type == "question":
        return "reanalyze"
    elif feedback_type == "modification":
        return "modify"
    else:
        return "continue"


def _build_multiagent_graph():
    """构建多智能体工作流图的基本结构"""
    # 创建状态图
    builder = StateGraph(State)
    
    # 添加所有节点 - 使用错误处理包装
    builder.add_node("context_analyzer", _wrap_node_with_error_handling(_context_analyzer_node))
    builder.add_node("objective_decomposer", _wrap_node_with_error_handling(_objective_decomposer_node))
    builder.add_node("task_analyzer", _wrap_node_with_error_handling(_task_analyzer_node))
    builder.add_node("sufficiency_evaluator", _wrap_node_with_error_handling(_sufficiency_evaluator_node))
    builder.add_node("research_agent", _wrap_node_with_error_handling(_research_agent_node))
    builder.add_node("processing_agent", _wrap_node_with_error_handling(_process_research_results))
    builder.add_node("quality_evaluator", _wrap_node_with_error_handling(_quality_evaluator_node))
    builder.add_node("synthesis_agent", _wrap_node_with_error_handling(_synthesis_agent_node))
    # builder.add_node("error_handler", _error_handler_node)  # 错误处理节点不需要包装
    builder.add_node("human_interaction", _wrap_node_with_error_handling(_human_interaction_node))
    builder.add_node("user_feedback", _wrap_node_with_error_handling(_user_feedback_node))
    builder.add_node("handle_feedback", _wrap_node_with_error_handling(_handle_user_feedback))
    
    # 添加边 - 主工作流程
    # 初始节点连接到上下文分析
    builder.add_edge(START, "context_analyzer")
    builder.add_edge("context_analyzer", "objective_decomposer")
    builder.add_edge("objective_decomposer", "task_analyzer")
    builder.add_edge("task_analyzer", "sufficiency_evaluator")
    
    # 添加条件边：充分性评估决定下一步
    builder.add_conditional_edges(
        "sufficiency_evaluator",
        _evaluate_sufficiency,
        {
            "sufficient": "research_agent",     # 如果任务设计充分，进入研究阶段
            "insufficient": "task_analyzer"     # 如果任务设计不充分，返回重新设计
        }
    )
    
    # 研究阶段的循环和处理阶段
    builder.add_conditional_edges(
        "research_agent",
        _evaluate_research_status,
        {
            "in_progress": "quality_evaluator", # 每完成一个研究任务，就进行质量评估
            "completed": "processing_agent",    # 如果所有研究任务已完成，进入处理阶段
            "no_tasks": "processing_agent"      # 如果没有待处理的任务，进入处理阶段
        }
    )
    
    # 质量评估后的分支
    builder.add_conditional_edges(
        "quality_evaluator",
        _evaluate_quality,
        {
            "passed": "research_agent",     # 如果质量评估通过，继续下一个研究任务
            "failed": "research_agent"      # 如果质量评估不通过，重新执行该研究任务
        }
    )
    
    # 处理阶段到合成阶段
    builder.add_edge("processing_agent", "synthesis_agent")
    
    # 合成阶段到用户反馈
    builder.add_edge("synthesis_agent", "user_feedback")
    
    # 用户反馈处理
    builder.add_conditional_edges(
        "user_feedback",
        _evaluate_user_feedback,
        {
            "reanalyze": "context_analyzer",  # 如果用户提出新问题，重新开始分析
            "modify": "handle_feedback",      # 如果用户要求修改，处理反馈
            "continue": END                   # 如果用户满意，结束流程
        }
    )
    
    # 处理用户反馈后的路径
    builder.add_edge("handle_feedback", "research_agent")  # 处理反馈后重新研究
    
    # 错误处理路径 - 条件路由
    # 为所有节点添加错误处理条件边
    # for node_name in [
    #     "context_analyzer", "objective_decomposer", "task_analyzer", 
    #     "sufficiency_evaluator", "research_agent", "processing_agent", 
    #     "quality_evaluator", "synthesis_agent", "human_interaction",
    #     "user_feedback", "handle_feedback"
    # ]:
    #     builder.add_conditional_edges(
    #         node_name,
    #         lambda state: "error_handler" if state.get("error") else node_name,
    #         {
    #             "error_handler": "error_handler",
    #             "context_analyzer": "context_analyzer",
    #             "objective_decomposer": "objective_decomposer",
    #             "task_analyzer": "task_analyzer",
    #             "sufficiency_evaluator": "sufficiency_evaluator",
    #             "research_agent": "research_agent",
    #             "processing_agent": "processing_agent",
    #             "quality_evaluator": "quality_evaluator",
    #             "synthesis_agent": "synthesis_agent",
    #             "human_interaction": "human_interaction",
    #             "user_feedback": "user_feedback",
    #             "handle_feedback": "handle_feedback"
    #         }
    #     )
    
    # # 错误处理节点的恢复路径
    # builder.add_conditional_edges(
    #     "error_handler",
    #     _determine_error_recovery_path,
    #     {
    #         "research_agent": "research_agent",
    #         "processing_agent": "processing_agent",
    #         "human_interaction": "human_interaction",
    #         "context_analyzer": "context_analyzer"
    #     }
    # )
    
    # 人机交互后回到上下文分析
    builder.add_edge("human_interaction", "context_analyzer")
    
    return builder


def build_multiagent_graph():
    """构建并编译多智能体工作流图"""
    # 构建图
    builder = _build_multiagent_graph()
    
    # 编译并返回
    return builder.compile()


def build_multiagent_graph_with_memory():
    """构建并编译带内存的多智能体工作流图"""
    # 使用持久内存保存会话历史
    memory = MemorySaver()
    
    # 构建图
    builder = _build_multiagent_graph()
    
    # 编译并返回
    return builder.compile(checkpointer=memory)