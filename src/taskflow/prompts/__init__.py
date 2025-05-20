# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow提示词模板模块。

提供各种智能体使用的提示词模板和工具函数。
"""

import os
import logging
from typing import Optional

# 获取日志记录器
logger = logging.getLogger(__name__)

# 导出常用模块
from src.taskflow.prompts.templates import (
    get_common_system_prompt,
    get_json_output_instruction,
    format_bulleted_list,
)

# 导出新的模板系统
from src.taskflow.prompts.template import (
    apply_prompt_template,
    get_prompt_template,
)

def load_prompt_from_file(file_path: str) -> Optional[str]:
    """
    从文件加载提示词模板。
    
    支持两种格式：
    1. 纯文本文件 (.txt)
    2. Markdown文件 (.md) - 会提取正文内容，忽略头部的元数据
    
    Args:
        file_path: 提示词文件路径
        
    Returns:
        提示词内容，如果文件不存在则返回None
    """
    try:
        if not os.path.exists(file_path):
            logger.warning(f"提示词文件不存在: {file_path}")
            return None
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
        if not content:
            logger.warning(f"提示词文件为空: {file_path}")
            return None
        
        # 处理markdown文件
        if file_path.endswith('.md'):
            # 尝试提取markdown的正文内容
            # 忽略前面的YAML元数据部分（如果有）
            if content.startswith('---'):
                # 查找第二个'---'分隔符，跳过元数据部分
                second_sep = content.find('---', 3)
                if second_sep != -1:
                    content = content[second_sep + 3:].strip()
            elif content.startswith('+++'):
                # 有些文件可能使用+++作为YAML前端分隔符
                second_sep = content.find('+++', 3)
                if second_sep != -1:
                    content = content[second_sep + 3:].strip()
            
            logger.info(f"Successfully loaded prompt from Markdown file: {file_path}")
        else:
            logger.info(f"Successfully loaded prompt file: {file_path}")
            
        return content
        
    except Exception as e:
        logger.error(f"Failed to load prompt file: {file_path}, error: {str(e)}")
        return None 