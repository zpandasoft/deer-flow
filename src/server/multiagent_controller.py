# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import json
import logging
import asyncio
from src.server.chat_request import (
    ChatMessage,
    ChatRequest,
    GeneratePodcastRequest,
    GeneratePPTRequest,
    GenerateProseRequest,
    MultiAgentStreamRequest,
    TTSRequest,
)
from typing import Dict, AsyncGenerator, Any, List, Optional, cast
from uuid import uuid4
import traceback

from langchain_core.messages import AIMessageChunk, ToolMessage

from src.graph.multiagent_builder import build_multiagent_graph_with_memory

logger = logging.getLogger(__name__)


def _make_event(event_type: str, data: Dict[str, Any]) -> str:
    """创建SSE事件字符串"""
    # 如果内容为空，则移除内容字段
    if "content" in data and data["content"] == "":
        data.pop("content")
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class MultiAgentStreamController:
    """多智能体流控制器"""
    
    def __init__(self):
        """初始化控制器"""
        # 初始化多智能体工作流图，使用workflow_graph而不是graph作为变量名
        # 这样可以避免与导入的context_analyzer_agent等名称冲突
        self.workflow_graph = build_multiagent_graph_with_memory()
        # 创建事件队列
        self.event_queue = asyncio.Queue()
        # 记录初始化成功信息
        logger.info("多智能体流控制器初始化成功，工作流图构建完成")
    
    async def _convert_workflow_event(self, agent: List[str], event_data: Any) -> Dict:
        """将工作流事件转换为API事件"""
        # 处理特殊字典类型事件
        if isinstance(event_data, dict):
            # 处理中断事件
            if "__interrupt__" in event_data:
                return {
                    "type": "interrupt",
                    "data": {
                        "thread_id": self.thread_id,
                        "id": event_data["__interrupt__"][0].ns[0],
                        "role": "assistant",
                        "content": event_data["__interrupt__"][0].value,
                        "finish_reason": "interrupt",
                        "options": [
                            {"text": "编辑计划", "value": "edit_plan"},
                            {"text": "继续执行", "value": "accepted"},
                        ],
                    }
                }
            # 处理目标创建事件
            elif "objective_created" in event_data:
                return {
                    "type": "objective_created",
                    "data": event_data["objective_created"]
                }
            # 处理任务创建事件
            elif "task_created" in event_data:
                return {
                    "type": "task_created",
                    "data": event_data["task_created"]
                }
            # 处理步骤创建事件
            elif "step_created" in event_data:
                return {
                    "type": "step_created",
                    "data": event_data["step_created"]
                }
            # 处理步骤完成事件
            elif "step_completed" in event_data:
                return {
                    "type": "step_completed",
                    "data": event_data["step_completed"]
                }
            # 处理最终结果事件
            elif "final_result" in event_data:
                return {
                    "type": "final_result",
                    "data": event_data["final_result"]
                }
            # 处理错误事件
            elif "error" in event_data:
                return {
                    "type": "error",
                    "data": event_data["error"]
                }
            # 处理进度更新事件
            elif "progress_update" in event_data:
                return {
                    "type": "progress_update",
                    "data": event_data["progress_update"]
                }
            # 处理其他字典类型事件
            return {
                "type": "state_update",
                "data": event_data
            }
        
        # 处理消息类型事件
        try:
            message_chunk, message_metadata = cast(
                tuple[AIMessageChunk, Dict[str, Any]], event_data
            )
            
            # 构建基本事件消息
            agent_name = agent[0].split(":")[0] if agent and len(agent) > 0 else "unknown"
            event_stream_message = {
                "thread_id": self.thread_id,
                "agent": agent_name,
                "id": message_chunk.id if hasattr(message_chunk, "id") else str(uuid4()),
                "role": "assistant",
                "content": message_chunk.content if hasattr(message_chunk, "content") else "",
            }
            
            # 处理不同类型的消息事件
            if isinstance(message_chunk, ToolMessage):
                # 工具消息 - 工具调用结果
                if hasattr(message_chunk, "tool_call_id"):
                    event_stream_message["tool_call_id"] = message_chunk.tool_call_id
                return {
                    "type": "tool_call_result",
                    "data": event_stream_message
                }
            elif hasattr(message_chunk, "tool_calls") and message_chunk.tool_calls:
                # AI消息 - 工具调用
                event_stream_message["tool_calls"] = message_chunk.tool_calls
                if hasattr(message_chunk, "tool_call_chunks"):
                    event_stream_message["tool_call_chunks"] = message_chunk.tool_call_chunks
                return {
                    "type": "tool_calls",
                    "data": event_stream_message
                }
            elif hasattr(message_chunk, "tool_call_chunks") and message_chunk.tool_call_chunks:
                # AI消息 - 工具调用片段
                event_stream_message["tool_call_chunks"] = message_chunk.tool_call_chunks
                return {
                    "type": "tool_call_chunks",
                    "data": event_stream_message
                }
            else:
                # 普通消息片段
                return {
                    "type": "message_chunk",
                    "data": event_stream_message
                }
        except Exception as e:
            logger.error(f"转换事件时出错: {str(e)}")
            return {
                "type": "error",
                "data": {
                    "message": f"事件转换错误: {str(e)}"
                }
            }
    
    async def _astream_multiagent_generator(
        self,
        messages: List[ChatMessage],
        thread_id: str,
        max_steps: int = 10,
        auto_execute: bool = False,
        interrupt_feedback: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """多智能体流生成器"""
        # 保存线程ID用于事件生成
        self.thread_id = thread_id
        
        # 准备初始状态
        input_ = {
            # "query": query,
#             "locale": locale,
            "max_steps": max_steps,
            "auto_execute": auto_execute,
            "additional_context": additional_context or {},
            "objectives": [],
            "tasks": [],
            "steps": [],
            "content_sufficient": False,
            "research_complete": False,
            "current_node": "context_analyzer",
            "messages": messages  # 添加空的messages列表，确保符合LangGraph要求
        }
        
        # 处理中断恢复
        if not auto_execute and interrupt_feedback:
            resume_msg = f"[{interrupt_feedback}]"
            # add the last message to the resume message
            if messages:
                 resume_msg += f" {messages[-1]['content']}"
            input_ = Command(resume=resume_msg)
        
        # 配置
        config = {
            "thread_id": thread_id,
            "max_steps": max_steps,
        }
        
        # 流式处理
        try:
            # 使用astream API流式执行工作流
            async for agent, _, event_data in self.workflow_graph.astream(
                input_,
                config=config,
                stream_mode=["messages", "updates"],
                subgraphs=True,
            ):
                # 转换事件
                event_info = await self._convert_workflow_event(agent, event_data)
                # 生成事件字符串
                yield _make_event(event_info["type"], event_info["data"])
                
        except Exception as e:
            error_message = str(e)
            error_traceback = traceback.format_exc()
            line_number = e.__traceback__.tb_lineno if hasattr(e, '__traceback__') and e.__traceback__ else 'unknown'
            
            logger.error(f"多智能体工作流执行错误: {error_message}")
            logger.error(f"文件: {__file__}, 行号: {line_number}")
            logger.error(f"堆栈跟踪:\n{error_traceback}")
            
            # 发送错误事件
            yield _make_event("error", {
                "message": f"工作流执行错误: {error_message}",
                "thread_id": thread_id,
                "file": __file__,
                "line": line_number,
            })