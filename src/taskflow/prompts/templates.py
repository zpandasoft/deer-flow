# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
提示词模板工具模块。

提供模板应用、变量替换和通用模板片段等功能。
"""

import re
from typing import Any, Dict, Optional


def apply_template(template: str, variables: Dict[str, Any]) -> str:
    """
    应用模板变量替换。
    
    将模板中的变量占位符 {{variable_name}} 替换为相应的值。
    
    Args:
        template: 包含变量占位符的模板字符串
        variables: 变量名到值的映射字典
        
    Returns:
        替换变量后的字符串
        
    Examples:
        >>> template = "你好，{{name}}！"
        >>> variables = {"name": "张三"}
        >>> apply_template(template, variables)
        '你好，张三！'
    """
    result = template
    
    # 使用正则表达式查找所有变量占位符
    # 格式为 {{variable_name}}
    pattern = r'{{([^{}]+)}}'
    
    # 查找所有匹配项
    for match in re.finditer(pattern, template):
        # 获取变量名（去除空白）
        var_name = match.group(1).strip()
        
        # 获取完整的匹配文本
        full_match = match.group(0)
        
        # 如果变量存在于字典中，则替换
        if var_name in variables:
            value = str(variables[var_name])
            result = result.replace(full_match, value)
    
    return result


def get_common_system_prompt() -> str:
    """
    获取通用系统提示词模板。
    
    提供适用于大多数智能体的基础系统提示词。
    
    Returns:
        通用系统提示词
    """
    return """
    你是一个专业的AI智能体，负责处理特定任务并提供高质量的输出。

    请严格按照指示行事，并确保你的输出符合要求的格式。
    关注细节，保持逻辑清晰，输出应直接切入主题。

    除非另有说明，所有输出都应使用中文。
    """


def get_json_output_instruction() -> str:
    """
    获取JSON输出格式说明。
    
    提供要求输出JSON格式的标准说明文本。
    
    Returns:
        JSON输出格式说明
    """
    return """
    所有输出必须是有效的JSON格式。确保你的回答只包含JSON对象，没有其他文本。
    不要添加代码块标记、注释或任何其他非JSON内容。
    """


def format_numbered_list(items: list) -> str:
    """
    格式化为编号列表。
    
    Args:
        items: 列表项
        
    Returns:
        格式化的编号列表字符串
    """
    if not items:
        return ""
    
    return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))


def format_bulleted_list(items: list) -> str:
    """
    格式化为项目符号列表。
    
    Args:
        items: 列表项
        
    Returns:
        格式化的项目符号列表字符串
    """
    if not items:
        return ""
    
    return "\n".join(f"• {item}" for item in items) 