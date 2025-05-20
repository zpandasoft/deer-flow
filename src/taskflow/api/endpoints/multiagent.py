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

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import StreamingResponse

from src.taskflow.api.schemas import MultiAgentStreamRequest
from src.taskflow.graph.multiagent_builder import build_multiagent_graph


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/stream")
async def multiagent_stream(request: MultiAgentStreamRequest):
    """
    多智能体流式处理API接口。
    
    接收用户查询（如"光伏组件出口法国需要完成哪些合规目标"），
    通过多智能体系统处理，流式返回处理结果。
    
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
            ),
            media_type="text/event-stream",
        )
    except Exception as e:
        logger.exception(f"Error initiating multiagent stream: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def _astream_multiagent_workflow_generator(
    query: str,
    thread_id: str,
    locale: str = "zh-CN",
    max_steps: int = 10,
    auto_execute: bool = False,
    interrupt_feedback: Optional[str] = None,
):
    """
    多智能体工作流事件流生成器。
    
    处理多智能体工作流事件并生成SSE事件流。
    
    参数:
        query: 用户查询
        thread_id: 会话ID
        locale: 区域设置
        max_steps: 最大步骤数
        auto_execute: 是否自动执行
        interrupt_feedback: 中断反馈
        
    生成:
        str: SSE事件字符串
    """
    try:
        # 构建工作流图
        graph = build_multiagent_graph()
        
        # 准备初始状态
        input_ = {
            "query": query,
            "messages": [],
            "locale": locale,
            "objectives": [],
            "tasks": [],
            "steps": [],
            "execution_results": {},
            "current_node": "context_analyzer",
            "auto_execute": auto_execute,
        }
        
        # 处理中断恢复
        if not auto_execute and interrupt_feedback:
            input_["interrupt_feedback"] = interrupt_feedback
        
        logger.info(f"Starting multiagent workflow with query: {query}")
        
        # 流式执行工作流
        async for agent, _, event_data in graph.astream(
            input_,
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
                # 状态更新事件
                yield _make_event("state_update", {
                    "thread_id": thread_id,
                    "agent": current_agent,
                    "id": str(uuid4()),
                    "state": event_data
                })
    
    except Exception as e:
        logger.exception(f"Error in multiagent workflow: {str(e)}")
        # 发送错误事件
        yield _make_event("error", {
            "thread_id": thread_id,
            "id": str(uuid4()),
            "error": str(e),
            "error_type": type(e).__name__
        })


def _make_event(event_type: str, data: Dict) -> str:
    """
    创建SSE事件字符串。
    
    参数:
        event_type: 事件类型
        data: 事件数据
        
    返回:
        str: 格式化的SSE事件字符串
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