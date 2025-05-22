#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
多智能体流式API简单测试脚本

通过发送请求到/api/v1/multiagent/stream接口，验证接口是否工作正常。
"""

import json
import sys
import requests
from sseclient import SSEClient

# 默认API地址
API_URL = "http://localhost:8000/api/v1/multiagent/stream"

def test_multiagent_api(query: str = "光伏组件出口法国需要完成哪些合规目标"):
    """测试多智能体API"""
    print(f"发送请求到 {API_URL}")
    print(f"查询: {query}\n")
    
    # 准备请求数据
    request_data = {
        "query": query,
        "thread_id": "__default__",
        "locale": "zh-CN",
        "max_steps": 10,
        "auto_execute": True
    }
    
    try:
        # 发送请求
        with requests.post(API_URL, json=request_data, stream=True) as response:
            response.raise_for_status()  # 检查请求是否成功
            
            # 使用SSEClient处理事件流
            client = SSEClient(response)
            for event in client.events():
                if event.event and event.data:
                    try:
                        # 解析事件数据
                        data = json.loads(event.data)
                        # 处理不同类型的事件
                        handle_event(event.event, data)
                    except json.JSONDecodeError:
                        print(f"错误: 无法解析事件数据: {event.data}")
    
    except requests.RequestException as e:
        print(f"请求错误: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("用户中断，退出程序")
        sys.exit(0)

def handle_event(event_type: str, data: dict):
    """处理不同类型的事件"""
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
        error = data.get("message", "")
        print(f"\n❌ 错误: {error}")
        
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

if __name__ == "__main__":
    # 如果命令行中提供了查询，则使用命令行查询
    query = sys.argv[1] if len(sys.argv) > 1 else "光伏组件出口法国需要完成哪些合规目标"
    test_multiagent_api(query) 