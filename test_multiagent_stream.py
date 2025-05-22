#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
多智能体流式API测试脚本

用于测试 /api/v1/multiagent/stream API接口的功能。
发送符合MultiAgentStreamRequest的请求并处理SSE流式响应。
"""

import argparse
import json
import logging
import sys
import time
from typing import Dict, Optional
from uuid import uuid4

import requests
from sseclient import SSEClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="测试多智能体流式API")
    parser.add_argument(
        "query", 
        type=str, 
        nargs="?", 
        default="光伏组件出口法国需要完成哪些合规目标",
        help="要提交的用户消息内容，将作为messages数组中的user消息"
    )
    parser.add_argument(
        "--api-url", 
        type=str, 
        # default="http://localhost:8000/api/chat/stream",
         default="http://localhost:8000/api/v1/multiagent/stream",
        help="API端点URL"
    )
    parser.add_argument(
        "--thread-id", 
        type=str, 
        default="__default__",
        help="会话ID，默认创建新会话"
    )
    parser.add_argument(
        "--locale", 
        type=str, 
        default="zh-CN",
        help="语言设置，默认中文"
    )
    parser.add_argument(
        "--max-steps", 
        type=int, 
        default=10,
        help="最大执行步骤数"
    )
    parser.add_argument(
        "--auto-execute", 
        action="store_true",
        help="是否自动执行所有步骤"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="启用详细日志"
    )
    parser.add_argument(
        "--use-sse-client", 
        action="store_true",
        help="使用SSEClient库处理事件流"
    )
    
    return parser.parse_args()


def prepare_request(args) -> Dict:
    """准备请求参数"""
    request_data = {
        "messages": [{"role": "user", "content": args.query}],
        "thread_id": args.thread_id,
        "locale": args.locale,
        "max_steps": args.max_steps,
        "auto_execute": args.auto_execute,
        "interrupt_feedback": None,
        "additional_context": None
    }
    
    return request_data


def handle_event(event_type: str, data: Dict, verbose: bool = False):
    """处理SSE事件"""
    if verbose:
        logger.info(f"收到事件: {event_type}")
        logger.info(f"事件数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
    # 基于事件类型进行特定处理
    if event_type == "message_chunk":
        content = data.get("content", "")
        agent = data.get("agent", "unknown")
        print(f"[{agent}] {content}")
        
    elif event_type == "objective_created":
        title = data.get("title", "")
        description = data.get("description", "")
        print(f"\n📌 目标创建: {title}")
        if description:
            print(f"   描述: {description}")
            
    elif event_type == "task_created":
        title = data.get("title", "")
        print(f"\n📋 任务创建: {title}")
        
    elif event_type == "step_created":
        title = data.get("title", "")
        step_type = data.get("step_type", "")
        print(f"\n🔍 步骤创建: [{step_type}] {title}")
        
    elif event_type == "step_completed":
        result = data.get("result", "")
        print(f"\n✅ 步骤完成: {result[:100]}..." if len(result) > 100 else f"\n✅ 步骤完成: {result}")
        
    elif event_type == "progress_update":
        progress = data.get("progress", 0)
        current_node = data.get("current_node", "")
        print(f"\r📊 进度: {progress}% [{current_node}]", end="")
        
    elif event_type == "error":
        error = data.get("error", "")
        suggestion = data.get("suggestion", "")
        print(f"\n❌ 错误: {error}")
        if suggestion:
            print(f"   建议: {suggestion}")
            
    elif event_type == "final_result":
        summary = data.get("summary", "")
        print(f"\n🏁 最终结果:")
        print(f"{summary}")
        
    elif event_type == "interrupt":
        content = data.get("content", "")
        options = data.get("options", [])
        print(f"\n⏸️ 中断: {content}")
        if options:
            print("   选项:")
            for i, option in enumerate(options):
                print(f"   {i+1}. {option.get('text')}")
    
    elif event_type == "tool_calls":
        tool_calls = data.get("tool_calls", [])
        if tool_calls:
            print(f"\n🔧 工具调用:")
            for tool_call in tool_calls:
                name = tool_call.get("name", "unknown")
                arguments = tool_call.get("arguments", {})
                print(f"   工具: {name}")
                print(f"   参数: {json.dumps(arguments, ensure_ascii=False)}")


def test_with_requests(api_url: str, request_data: Dict, verbose: bool = False):
    """使用基础requests库测试API"""
    try:
        with requests.post(api_url, json=request_data, stream=True) as response:
            response.raise_for_status()  # 检查请求是否成功
            
            # 手动解析SSE响应
            buffer = ""
            for chunk in response.iter_content(chunk_size=1):
                if chunk:
                    chunk_str = chunk.decode('utf-8')
                    buffer += chunk_str
                    
                    if buffer.endswith('\n\n'):
                        # 解析事件
                        lines = buffer.strip().split('\n')
                        event_type = None
                        event_data = None
                        
                        for line in lines:
                            if line.startswith('event:'):
                                event_type = line[6:].strip()
                            elif line.startswith('data:'):
                                event_data = line[5:].strip()
                        
                        if event_type and event_data:
                            try:
                                data = json.loads(event_data)
                                handle_event(event_type, data, verbose)
                            except json.JSONDecodeError:
                                logger.error(f"无法解析事件数据: {event_data}")
                        
                        # 重置缓冲区
                        buffer = ""
                        
    except requests.RequestException as e:
        logger.error(f"请求错误: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("用户中断，退出程序")
        sys.exit(0)


def test_with_sseclient(api_url: str, request_data: Dict, verbose: bool = False):
    """使用SSEClient库测试API"""
    try:
        response = requests.post(api_url, json=request_data, stream=True)
        response.raise_for_status()  # 检查请求是否成功
        
        client = SSEClient(response)
        for event in client.events():
            if event.event and event.data:
                try:
                    data = json.loads(event.data)
                    handle_event(event.event, data, verbose)
                except json.JSONDecodeError:
                    logger.error(f"无法解析事件数据: {event.data}")
    
    except requests.RequestException as e:
        logger.error(f"请求错误: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("用户中断，退出程序")
        sys.exit(0)


def main():
    """主函数"""
    args = parse_arguments()
    
    # 设置日志级别
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # 准备请求参数
    request_data = prepare_request(args)
    
    # 记录请求信息
    logger.info(f"发送请求到: {args.api_url}")
    logger.info(f"用户消息: {args.query}")
    
    # 根据参数选择测试方式
    print(f"request_data: {request_data}\n")
    if args.use_sse_client:
        try:
            import sseclient
            test_with_sseclient(args.api_url, request_data, args.verbose)
        except ImportError:
            logger.warning("未安装sseclient库，将使用基础requests库")
            test_with_requests(args.api_url, request_data, args.verbose)
    else:
        test_with_requests(args.api_url, request_data, args.verbose)


if __name__ == "__main__":
    main() 