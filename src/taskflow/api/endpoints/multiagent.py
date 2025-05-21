# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
多智能体API接口。

提供多智能体流式处理接口，支持复杂研究问题的处理和流式结果返回。
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import StreamingResponse

from src.taskflow.api.schemas import MultiAgentStreamRequest
from src.taskflow.graph.multiagent_builder import build_multiagent_graph
from src.taskflow.graph.types import TaskState, WorkflowMetadata, ObjectiveState, ObjectiveStatus


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/stream")
async def multiagent_stream(request: MultiAgentStreamRequest):
    """
    多智能体流式处理API接口。
    
    接收用户查询（如"光伏组件出口法国需要完成哪些合规目标"），
    通过多智能体系统处理，流式返回处理结果。
    
    支持以下事件类型：
    - agent_start: 智能体开始执行
    - agent_output: 智能体输出结果
    - objective_created: 创建了新的研究目标
    - task_created: 创建了新的任务
    - step_created: 创建了新的步骤
    - step_completed: 完成了步骤执行
    - error: 发生错误
    - final_result: 最终结果
    
    参数:
        request: 流式请求对象
        
    返回:
        StreamingResponse: 流式响应对象
    """
    # 处理会话ID
    thread_id = request.thread_id
    if thread_id == "__default__":
        thread_id = str(uuid4())
    
    try:
        # 返回流式响应
        return StreamingResponse(
            _astream_multiagent_workflow_generator(
                query=request.query,
                thread_id=thread_id,
                locale=request.locale,
                max_steps=request.max_steps,
                auto_execute=request.auto_execute,
                interrupt_feedback=request.interrupt_feedback,
                additional_context=request.additional_context,
            ),
            media_type="text/event-stream",
        )
    except Exception as e:
        logger.exception(f"Error initiating multiagent stream: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def _calculate_progress(state: Dict) -> float:
    """
    计算工作流执行进度。
    
    根据目标、任务和步骤的完成情况计算总体进度。
    
    参数:
        state: 工作流状态
        
    返回:
        float: 进度百分比（0-100）
    """
    # 默认权重
    weights = {
        "context_analyzer": 5,
        "objective_decomposer": 10,
        "task_analyzer": 15,
        "research": 30,
        "quality_evaluator": 10,
        "processing": 20,
        "synthesis": 10,
    }
    
    # 获取当前节点和访问历史
    current_node = state.get("current_node", "")
    visited_nodes = state.get("visited_nodes", [])
    
    # 基于已访问节点计算进度
    progress = 0
    total_weight = sum(weights.values())
    
    for node, weight in weights.items():
        if node in visited_nodes or node == current_node:
            progress += weight
    
    # 归一化为百分比
    return min(100, round((progress / total_weight) * 100, 1))


async def _astream_multiagent_workflow_generator(
    query: str,
    thread_id: str,
    locale: str = "zh-CN",
    max_steps: int = 10,
    auto_execute: bool = False,
    interrupt_feedback: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None,
):
    """
    多智能体工作流事件流生成器。
    
    处理多智能体工作流事件并生成SSE事件流。该生成器会流式返回工作流执行过程中的各类事件，
    包括智能体启动、输出结果、目标创建、任务创建、步骤执行等。通过这些事件，客户端可以
    实时获取研究问题处理的进展和结果。
    
    支持的事件类型：
    - agent_start: 智能体开始执行
    - agent_output: 智能体输出结果
    - objective_created: 创建了新的研究目标
    - task_created: 创建了新的任务
    - step_created: 创建了新的步骤
    - step_completed: 完成了步骤执行
    - progress_update: 进度更新
    - error: 发生错误
    - final_result: 最终结果
    
    参数:
        query: 用户查询/研究问题
        thread_id: 会话ID，用于关联多次交互
        locale: 区域设置，默认为"zh-CN"
        max_steps: 最大执行步骤数，默认为10
        auto_execute: 是否自动执行所有步骤，默认为false
        interrupt_feedback: 中断反馈信息
        additional_context: 额外上下文信息，用于提供更多背景
        
    生成:
        str: 格式化的SSE事件字符串
    """
    try:
        # 构建工作流图
        graph = build_multiagent_graph()
        
        # 创建工作流元数据
        workflow_metadata = WorkflowMetadata(
            workflow_id=f"wf-{uuid4()}",
            workflow_type="multiagent",
            user_id=None,
            tags=[]
        )
        
        # 创建目标状态
        objective = ObjectiveState(
            objective_id=f"obj-{uuid4()}",
            title=query[:50] + ("..." if len(query) > 50 else ""),
            query=query,
            status=ObjectiveStatus.CREATED
        )
        
        # 创建初始TaskState
        input_state = TaskState(
            workflow_metadata=workflow_metadata,
            objective=objective,
            messages=[],
            intermediate_data={
                "locale": locale,
                "auto_execute": auto_execute,
                "additional_context": additional_context or {},
            }
        )
        
        # 处理中断恢复
        if not auto_execute and interrupt_feedback:
            input_state.intermediate_data["interrupt_feedback"] = interrupt_feedback
        
        logger.info(f"Starting multiagent workflow with query: {query}")
        
        # 流式执行工作流
        async for agent, _, event_data in graph.astream(
            input_state,
            config={
                "thread_id": thread_id,
                "max_steps": max_steps,
            },
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ):
            # 获取当前节点
            current_agent = agent[0].split(":")[0] if agent and agent[0] else "system"
            
            # 处理中断事件
            if isinstance(event_data, dict) and "__interrupt__" in event_data:
                interrupt_data = event_data["__interrupt__"][0]
                logger.info(f"Interrupt event from {current_agent}")
                
                yield _make_event(
                    "interrupt", 
                    {
                        "thread_id": thread_id,
                        "id": getattr(interrupt_data, 'ns', [str(uuid4())])[0],
                        "role": "assistant",
                        "agent": current_agent,
                        "content": getattr(interrupt_data, 'value', str(interrupt_data)),
                        "finish_reason": "interrupt",
                        "options": [
                            {"text": "编辑计划", "value": "edit_plan"},
                            {"text": "开始执行", "value": "accepted"},
                        ],
                    }
                )
                continue
            
            # 处理消息事件
            if event_data and hasattr(event_data, "__len__") and len(event_data) >= 1:
                message_chunk = event_data[0] if isinstance(event_data, (list, tuple)) else event_data
                
                # 准备事件数据
                event_stream_message = {
                    "thread_id": thread_id,
                    "agent": current_agent,
                    "id": getattr(message_chunk, 'id', str(uuid4())),
                    "role": "assistant",
                }
                
                # 提取内容
                if hasattr(message_chunk, 'content'):
                    event_stream_message["content"] = message_chunk.content
                else:
                    # 尝试将对象转换为字符串
                    event_stream_message["content"] = str(message_chunk)
                
                # 添加finish_reason（如果存在）
                if hasattr(message_chunk, 'response_metadata') and message_chunk.response_metadata.get("finish_reason"):
                    event_stream_message["finish_reason"] = message_chunk.response_metadata.get("finish_reason")
                
                # 处理工具调用
                if hasattr(message_chunk, 'tool_call_id') and message_chunk.tool_call_id:
                    # 工具调用结果
                    event_stream_message["tool_call_id"] = message_chunk.tool_call_id
                    yield _make_event("tool_call_result", event_stream_message)
                elif hasattr(message_chunk, 'tool_calls') and message_chunk.tool_calls:
                    # 工具调用
                    event_stream_message["tool_calls"] = message_chunk.tool_calls
                    if hasattr(message_chunk, 'tool_call_chunks'):
                        event_stream_message["tool_call_chunks"] = message_chunk.tool_call_chunks
                    yield _make_event("tool_calls", event_stream_message)
                elif hasattr(message_chunk, 'tool_call_chunks') and message_chunk.tool_call_chunks:
                    # 工具调用块
                    event_stream_message["tool_call_chunks"] = message_chunk.tool_call_chunks
                    yield _make_event("tool_call_chunks", event_stream_message)
                else:
                    # 普通消息块
                    yield _make_event("message_chunk", event_stream_message)
            
            # 处理状态更新事件
            elif isinstance(event_data, dict) and not "__interrupt__" in event_data:
                # 计算当前进度
                progress = _calculate_progress(event_data)
                
                # 发送进度更新事件
                yield _make_event("progress_update", {
                    "thread_id": thread_id,
                    "id": str(uuid4()),
                    "progress": progress,
                    "current_node": event_data.get("current_node", "unknown"),
                    "timestamp": datetime.now().isoformat()
                })
                
                # 检查是否是特定类型的状态更新
                # 检查是否包含新创建的目标
                if "objective_created" in event_data:
                    objective = event_data["objective_created"]
                    yield _make_event("objective_created", {
                        "thread_id": thread_id,
                        "id": str(uuid4()),
                        "objective_id": objective.get("objective_id", str(uuid4())),
                        "title": objective.get("title", "未命名目标"),
                        "description": objective.get("description", "")
                    })
                    
                # 检查是否包含新创建的任务
                elif "task_created" in event_data:
                    task = event_data["task_created"]
                    yield _make_event("task_created", {
                        "thread_id": thread_id,
                        "id": str(uuid4()),
                        "task_id": task.get("task_id", str(uuid4())),
                        "objective_id": task.get("objective_id", ""),
                        "title": task.get("title", "未命名任务"),
                        "description": task.get("description", ""),
                        "status": task.get("status", "PENDING")
                    })
                    
                # 检查是否包含新创建的步骤
                elif "step_created" in event_data:
                    step = event_data["step_created"]
                    yield _make_event("step_created", {
                        "thread_id": thread_id,
                        "id": str(uuid4()),
                        "step_id": step.get("step_id", str(uuid4())),
                        "task_id": step.get("task_id", ""),
                        "title": step.get("title", "未命名步骤"),
                        "description": step.get("description", ""),
                        "step_type": step.get("step_type", "RESEARCH"),
                        "status": step.get("status", "PENDING")
                    })
                    
                # 检查是否包含已完成的步骤
                elif "step_completed" in event_data:
                    step = event_data["step_completed"]
                    result = event_data.get("result", {})
                    yield _make_event("step_completed", {
                        "thread_id": thread_id,
                        "id": str(uuid4()),
                        "step_id": step.get("step_id", ""),
                        "result": result.get("content", "无结果内容"),
                        "quality_score": result.get("quality_score", 0),
                        "sources": result.get("sources", [])
                    })
                    
                # 检查是否是最终结果
                elif "final_result" in event_data:
                    result = event_data["final_result"]
                    yield _make_event("final_result", {
                        "thread_id": thread_id,
                        "id": str(uuid4()),
                        "summary": result.get("summary", "无摘要内容"),
                        "objectives": event_data.get("objectives", []),
                        "tasks": event_data.get("tasks", []),
                        "steps": event_data.get("steps", [])
                    })
                    
                # 默认状态更新事件
                else:
                    yield _make_event("state_update", {
                        "thread_id": thread_id,
                        "agent": current_agent,
                        "id": str(uuid4()),
                        "state": event_data
                    })
    
    except Exception as e:
        logger.exception(f"Error in multiagent workflow: {str(e)}")
        
        # 分析错误类型，提供更详细的错误信息
        error_info = {
            "thread_id": thread_id,
            "id": str(uuid4()),
            "error": str(e),
            "error_type": type(e).__name__,
            "timestamp": datetime.now().isoformat()
        }
        
        # 根据不同错误类型添加特定信息
        if "WorkflowStateError" in type(e).__name__:
            error_info["suggestion"] = "工作流状态错误，请尝试使用新的thread_id重新开始"
        elif "AgentError" in type(e).__name__:
            error_info["suggestion"] = "智能体执行错误，可能是输入格式问题，请检查查询格式"
        elif "timeout" in str(e).lower():
            error_info["suggestion"] = "执行超时，请考虑简化查询或增加max_steps参数"
        else:
            error_info["suggestion"] = "发生未知错误，请尝试重新提交请求"
        
        # 发送错误事件
        yield _make_event("error", error_info)


def _make_event(event_type: str, data: Dict) -> str:
    """
    创建SSE事件字符串。
    
    将事件类型和数据格式化为Server-Sent Events (SSE)格式的字符串。
    支持的事件类型包括：
    - agent_start: 智能体开始执行
    - agent_output: 智能体输出结果
    - message_chunk: 消息块
    - tool_calls: 工具调用
    - tool_call_chunks: 工具调用块
    - tool_call_result: 工具调用结果
    - interrupt: 中断事件
    - objective_created: 创建了新的研究目标
    - task_created: 创建了新的任务
    - step_created: 创建了新的步骤
    - step_completed: 完成了步骤执行
    - progress_update: 进度更新
    - state_update: 状态更新
    - error: 错误事件
    - final_result: 最终结果
    
    参数:
        event_type: 事件类型
        data: 事件数据
        
    返回:
        str: 格式化的SSE事件字符串，格式为"event: {事件类型}\ndata: {JSON格式的事件数据}\n\n"
    """
    try:
        event_data = json.dumps(data)
        return f"event: {event_type}\ndata: {event_data}\n\n"
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}")
        # 提供后备实现
        simplified_data = {
            "thread_id": data.get("thread_id", "unknown"),
            "error": f"Error serializing event data: {str(e)}"
        }
        return f"event: error\ndata: {json.dumps(simplified_data)}\n\n" 