# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
提示词模板系统模块。

提供Jinja2模板加载、变量替换和其他模板处理功能。
"""

import os
import dataclasses
from datetime import datetime
from typing import Any, Dict, List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

# 初始化Jinja2环境
templates_dirs = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "prompts"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
]

env = Environment(
    loader=FileSystemLoader(templates_dirs),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def get_prompt_template(prompt_name: str) -> str:
    """
    加载并返回提示词模板。
    
    Args:
        prompt_name: 提示词模板文件名（不带.md扩展名）
    
    Returns:
        带有适当变量替换语法的模板字符串
        
    Raises:
        ValueError: 如果模板加载失败
    """
    try:
        template = env.get_template(f"{prompt_name}.md")
        return template.render()
    except Exception as e:
        raise ValueError(f"加载模板{prompt_name}时出错: {e}")


def apply_prompt_template(
    prompt_name: str, state: Dict[str, Any], configurable: Optional[Any] = None
) -> List[Dict[str, str]]:
    """
    将模板变量应用到提示词模板，并返回格式化的消息列表。
    
    Args:
        prompt_name: 要使用的提示词模板名称
        state: 包含要替换变量的当前状态
        configurable: 可选的配置对象
        
    Returns:
        以系统提示作为第一条消息的消息列表
        
    Raises:
        ValueError: 如果模板应用失败
    """
    # 转换状态为字典，用于模板渲染
    state_vars = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        **state,
    }
    
    # 添加配置变量
    if configurable:
        if hasattr(configurable, "__dataclass_fields__"):
            state_vars.update(dataclasses.asdict(configurable))
        elif isinstance(configurable, dict):
            state_vars.update(configurable)
    
    try:
        template = env.get_template(f"{prompt_name}.md")
        system_prompt = template.render(**state_vars)
        
        # 创建消息列表
        messages = [{"role": "system", "content": system_prompt}]
        
        # 添加state中的现有消息（如果有）
        if "messages" in state and isinstance(state["messages"], list):
            messages.extend(state["messages"])
        
        return messages
    except Exception as e:
        raise ValueError(f"应用模板{prompt_name}时出错: {e}") 