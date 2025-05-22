# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import base64
import json
import logging
import os
import traceback
from typing import List, cast, Dict, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from langchain_core.messages import AIMessageChunk, ToolMessage
from langgraph.types import Command

from src.graph.builder import build_graph_with_memory
from src.graph.multiagent_builder import build_multiagent_graph_with_memory
from src.podcast.graph.builder import build_graph as build_podcast_graph
from src.ppt.graph.builder import build_graph as build_ppt_graph
from src.prose.graph.builder import build_graph as build_prose_graph
from src.server.chat_request import (
    ChatMessage,
    ChatRequest,
    GeneratePodcastRequest,
    GeneratePPTRequest,
    GenerateProseRequest,
    MultiAgentStreamRequest,
    TTSRequest,
)
from src.server.mcp_request import MCPServerMetadataRequest, MCPServerMetadataResponse
from src.server.mcp_utils import load_mcp_tools
from src.server.multiagent_controller import MultiAgentStreamController
from src.tools import VolcengineTTS

logger = logging.getLogger(__name__)

app = FastAPI(
    title="DeerFlow API",
    description="API for Deer",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

graph = build_graph_with_memory()
multiagent_controller = MultiAgentStreamController()


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    thread_id = request.thread_id
    if thread_id == "__default__":
        thread_id = str(uuid4())
    return StreamingResponse(
        _astream_workflow_generator(
            request.model_dump()["messages"],
            thread_id,
            request.max_plan_iterations,
            request.max_step_num,
            request.auto_accepted_plan,
            request.interrupt_feedback,
            request.mcp_settings,
            request.enable_background_investigation,
        ),
        media_type="text/event-stream",
    )


async def _astream_workflow_generator(
    messages: List[ChatMessage],
    thread_id: str,
    max_plan_iterations: int,
    max_step_num: int,
    auto_accepted_plan: bool,
    interrupt_feedback: str,
    mcp_settings: dict,
    enable_background_investigation,
):
    input_ = {
        "messages": messages,
        "plan_iterations": 0,
        "final_report": "",
        "current_plan": None,
        "observations": [],
        "auto_accepted_plan": auto_accepted_plan,
        "enable_background_investigation": enable_background_investigation,
    }
    if not auto_accepted_plan and interrupt_feedback:
        resume_msg = f"[{interrupt_feedback}]"
        # add the last message to the resume message
        if messages:
            resume_msg += f" {messages[-1]['content']}"
        input_ = Command(resume=resume_msg)
    async for agent, _, event_data in graph.astream(
        input_,
        config={
            "thread_id": thread_id,
            "max_plan_iterations": max_plan_iterations,
            "max_step_num": max_step_num,
            "mcp_settings": mcp_settings,
        },
        stream_mode=["messages", "updates"],
        subgraphs=True,
    ):
        if isinstance(event_data, dict):
            if "__interrupt__" in event_data:
                yield _make_event(
                    "interrupt",
                    {
                        "thread_id": thread_id,
                        "id": event_data["__interrupt__"][0].ns[0],
                        "role": "assistant",
                        "content": event_data["__interrupt__"][0].value,
                        "finish_reason": "interrupt",
                        "options": [
                            {"text": "Edit plan", "value": "edit_plan"},
                            {"text": "Start research", "value": "accepted"},
                        ],
                    },
                )
            continue
        message_chunk, message_metadata = cast(
            tuple[AIMessageChunk, dict[str, any]], event_data
        )
        event_stream_message: dict[str, any] = {
            "thread_id": thread_id,
            "agent": agent[0].split(":")[0],
            "id": message_chunk.id,
            "role": "assistant",
            "content": message_chunk.content,
        }
        if message_chunk.response_metadata.get("finish_reason"):
            event_stream_message["finish_reason"] = message_chunk.response_metadata.get(
                "finish_reason"
            )
        if isinstance(message_chunk, ToolMessage):
            # Tool Message - Return the result of the tool call
            event_stream_message["tool_call_id"] = message_chunk.tool_call_id
            yield _make_event("tool_call_result", event_stream_message)
        else:
            # AI Message - Raw message tokens
            if message_chunk.tool_calls:
                # AI Message - Tool Call
                event_stream_message["tool_calls"] = message_chunk.tool_calls
                event_stream_message["tool_call_chunks"] = (
                    message_chunk.tool_call_chunks
                )
                yield _make_event("tool_calls", event_stream_message)
            elif message_chunk.tool_call_chunks:
                # AI Message - Tool Call Chunks
                event_stream_message["tool_call_chunks"] = (
                    message_chunk.tool_call_chunks
                )
                yield _make_event("tool_call_chunks", event_stream_message)
            else:
                # AI Message - Raw message tokens
                yield _make_event("message_chunk", event_stream_message)


def _make_event(event_type: str, data: dict[str, any]):
    if data.get("content") == "":
        data.pop("content")
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using volcengine TTS API."""
    try:
        app_id = os.getenv("VOLCENGINE_TTS_APPID", "")
        if not app_id:
            raise HTTPException(
                status_code=400, detail="VOLCENGINE_TTS_APPID is not set"
            )
        access_token = os.getenv("VOLCENGINE_TTS_ACCESS_TOKEN", "")
        if not access_token:
            raise HTTPException(
                status_code=400, detail="VOLCENGINE_TTS_ACCESS_TOKEN is not set"
            )
        cluster = os.getenv("VOLCENGINE_TTS_CLUSTER", "volcano_tts")
        voice_type = os.getenv("VOLCENGINE_TTS_VOICE_TYPE", "BV700_V2_streaming")

        tts_client = VolcengineTTS(
            appid=app_id,
            access_token=access_token,
            cluster=cluster,
            voice_type=voice_type,
        )
        # Call the TTS API
        result = tts_client.text_to_speech(
            text=request.text[:1024],
            encoding=request.encoding,
            speed_ratio=request.speed_ratio,
            volume_ratio=request.volume_ratio,
            pitch_ratio=request.pitch_ratio,
            text_type=request.text_type,
            with_frontend=request.with_frontend,
            frontend_type=request.frontend_type,
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=str(result["error"]))

        # Decode the base64 audio data
        audio_data = base64.b64decode(result["audio_data"])

        # Return the audio file
        return Response(
            content=audio_data,
            media_type=f"audio/{request.encoding}",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=tts_output.{request.encoding}"
                )
            },
        )
    except Exception as e:
        logger.exception(f"Error in TTS endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/podcast/generate")
async def generate_podcast(request: GeneratePodcastRequest):
    try:
        report_content = request.content
        print(report_content)
        workflow = build_podcast_graph()
        final_state = workflow.invoke({"input": report_content})
        audio_bytes = final_state["output"]
        return Response(content=audio_bytes, media_type="audio/mp3")
    except Exception as e:
        logger.exception(f"Error occurred during podcast generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ppt/generate")
async def generate_ppt(request: GeneratePPTRequest):
    try:
        report_content = request.content
        print(report_content)
        workflow = build_ppt_graph()
        final_state = workflow.invoke({"input": report_content})
        generated_file_path = final_state["generated_file_path"]
        with open(generated_file_path, "rb") as f:
            ppt_bytes = f.read()
        return Response(
            content=ppt_bytes,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    except Exception as e:
        logger.exception(f"Error occurred during ppt generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/prose/generate")
async def generate_prose(request: GenerateProseRequest):
    try:
        logger.info(f"Generating prose for prompt: {request.prompt}")
        workflow = build_prose_graph()
        events = workflow.astream(
            {
                "content": request.prompt,
                "option": request.option,
                "command": request.command,
            },
            stream_mode="messages",
            subgraphs=True,
        )
        return StreamingResponse(
            (f"data: {event[0].content}\n\n" async for _, event in events),
            media_type="text/event-stream",
        )
    except Exception as e:
        logger.exception(f"Error occurred during prose generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mcp/server/metadata", response_model=MCPServerMetadataResponse)
async def mcp_server_metadata(request: MCPServerMetadataRequest):
    """Get information about an MCP server."""
    try:
        # Set default timeout with a longer value for this endpoint
        timeout = 300  # Default to 300 seconds for this endpoint

        # Use custom timeout from request if provided
        if request.timeout_seconds is not None:
            timeout = request.timeout_seconds

        # Load tools from the MCP server using the utility function
        tools = await load_mcp_tools(
            server_type=request.transport,
            command=request.command,
            args=request.args,
            url=request.url,
            env=request.env,
            timeout_seconds=timeout,
        )

        # Create the response with tools
        response = MCPServerMetadataResponse(
            transport=request.transport,
            command=request.command,
            args=request.args,
            url=request.url,
            env=request.env,
            tools=tools,
        )

        return response
    except Exception as e:
        if not isinstance(e, HTTPException):
            logger.exception(f"Error in MCP server metadata endpoint: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        raise


@app.post("/api/v1/multiagent/stream")
async def multiagent_stream(request: ChatRequest):
    """多智能体研究流接口"""
    thread_id = request.thread_id
    if thread_id == "__default__":
        thread_id = str(uuid4())
    
    # 创建多智能体工作流图
    multiagent_graph = build_multiagent_graph_with_memory()
    
    # 准备初始状态
    input_ = {
        "messages": request.model_dump()["messages"],
        "max_steps": request.max_step_num,
        "auto_execute": request.auto_accepted_plan,
        "additional_context": request.mcp_settings or {},
        "objectives": [],
        "tasks": [],
        "steps": [],
        "content_sufficient": False,
        "research_complete": False,
        "current_node": "context_analyzer"  # 确保从context_analyzer开始
    }
    
    # 处理中断恢复
    if not request.auto_accepted_plan and request.interrupt_feedback:
        resume_msg = f"[{request.interrupt_feedback}]"
        if input_["messages"]:
            last_message = input_["messages"][-1]
            resume_msg += f" {last_message['content']}"
        # 使用Command对象创建适当的中断恢复格式
        from langgraph.graph import Command
        input_ = Command(resume=resume_msg)
    
    # 配置
    config = {
        "thread_id": thread_id,
        "max_steps": request.max_step_num,
    }
    
    # 流式处理
    return StreamingResponse(
        _multiagent_stream_generator(multiagent_graph, input_, config, thread_id),
        media_type="text/event-stream"
    )

async def _multiagent_stream_generator(workflow_graph, input_, config, thread_id):
    """多智能体流生成器"""
    try:
        # 使用astream API流式执行工作流
        async for agent, _, event_data in workflow_graph.astream(
            input_,
            config=config,
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ):
            # 转换事件
            event_info = await _convert_multiagent_event(agent, "event", event_data, thread_id)
            # 生成事件字符串
            yield f"data: {json.dumps(event_info, ensure_ascii=False)}\n\n"
    except Exception as e:
        error_message = str(e)
        error_traceback = traceback.format_exc()
        line_number = e.__traceback__.tb_lineno if hasattr(e, '__traceback__') and e.__traceback__ else 'unknown'
        
        logger.error(f"多智能体工作流执行错误: {error_message}")
        logger.error(f"文件: {__file__}, 行号: {line_number}")
        logger.error(f"堆栈跟踪:\n{error_traceback}")
        
        # 发送错误事件
        yield f"data: {json.dumps({'type': 'error', 'data': {'message': f'工作流执行错误: {error_message}', 'thread_id': thread_id, 'file': __file__, 'line': line_number}}, ensure_ascii=False)}\n\n"

async def _convert_multiagent_event(agent, event_type, event_data, thread_id):
    """将工作流事件转换为API事件"""
    # 处理特殊字典类型事件
    if isinstance(event_data, dict):
        # 处理中断事件
        if "__interrupt__" in event_data:
            return {
                "type": "interrupt",
                "data": {
                    "thread_id": thread_id,
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
        # 处理其他字典类型事件
        return {
            "type": "state_update",
            "data": event_data
        }
    
    # 处理消息类型事件
    try:
        # 适用不同类型的消息处理
        if hasattr(event_data, 'content'):
            # 构建基本事件消息
            agent_name = agent[0].split(":")[0] if agent and len(agent) > 0 else "unknown"
            return {
                "type": "message_chunk",
                "data": {
                    "thread_id": thread_id,
                    "agent": agent_name,
                    "id": event_data.id if hasattr(event_data, "id") else str(uuid4()),
                    "role": "assistant",
                    "content": event_data.content
                }
            }
        else:
            # 其他类型的事件
            return {
                "type": "other_event",
                "data": str(event_data)
            }
    except Exception as e:
        logger.error(f"转换事件时出错: {str(e)}")
        return {
            "type": "error",
            "data": {
                "message": f"事件转换错误: {str(e)}",
                "thread_id": thread_id,
                "file": __file__,
                "line": 391
            }
        }
