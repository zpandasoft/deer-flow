# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
处理智能体提示词模板模块。

提供数据处理和转换相关的提示词模板。
"""

from typing import Dict, Any

from src.taskflow.prompts.templates import get_json_output_instruction


def get_processing_system_prompt() -> str:
    """
    获取处理智能体的默认系统提示词。
    
    Returns:
        系统提示词
    """
    return """
    你是一个专业的数据处理智能体，负责处理和转换各类数据。
    
    你的主要任务是：
    1. 对输入数据进行清洗、规范化和格式转换
    2. 提取关键信息并进行结构化
    3. 根据需求进行数据聚合和统计
    4. 将处理结果输出为指定格式
    
    请严格按照指示处理数据，并确保输出格式正确。
    处理时注意保留关键信息，去除冗余和无关内容。
    """


def get_text_processing_prompt(processing_type: str, extra_instructions: str = "") -> str:
    """
    获取文本处理提示词。
    
    Args:
        processing_type: 处理类型，如'summarize'、'extract'、'classify'等
        extra_instructions: 额外指示
        
    Returns:
        文本处理提示词
    """
    prompt_templates = {
        "summarize": """
        请对以下文本进行摘要总结，保留核心信息，去除冗余内容。
        总结应当简洁明了，但包含所有关键点。
        输出格式为JSON，包含以下字段：
        - summary: 总结文本
        - key_points: 关键点列表
        - source_length: 原文长度（字符数）
        - summary_length: 总结长度（字符数）
        - compression_ratio: 压缩比例
        """,
        "extract": """
        请从以下文本中提取关键信息，包括但不限于：
        - 实体（人名、组织、地点等）
        - 日期和时间
        - 数值数据
        - 专业术语
        
        输出格式为JSON，包含以下字段：
        - entities: 提取的实体列表，每个实体包含名称、类型和出现次数
        - dates: 提取的日期列表
        - numerical_data: 提取的数值数据，包含值和单位
        - terms: 提取的专业术语列表
        """,
        "classify": """
        请对以下文本进行分类，确定其主题、情感倾向和内容类型。
        
        输出格式为JSON，包含以下字段：
        - category: 主题分类
        - sentiment: 情感倾向（正面、负面或中性）
        - content_type: 内容类型（新闻、学术、观点等）
        - confidence: 分类置信度（0-1之间的浮点数）
        - keywords: 支持分类判断的关键词列表
        """,
        "standardize": """
        请对以下文本进行标准化处理，包括：
        - 纠正拼写和语法错误
        - 统一格式和术语
        - 规范化表达方式
        - 整理段落和结构
        
        输出格式为JSON，包含以下字段：
        - standardized_text: 标准化后的文本
        - corrections: 进行的更正列表，每项包含原文和更正后的文本
        - quality_score: 原文质量评分（1-10）
        """,
    }
    
    base_prompt = prompt_templates.get(
        processing_type,
        "请对以下文本进行处理，提取有价值的信息并输出为结构化格式。"
    )
    
    # 添加额外指示（如果有）
    if extra_instructions:
        base_prompt += f"\n\n{extra_instructions}"
    
    # 添加JSON输出指示
    base_prompt += f"\n\n{get_json_output_instruction()}"
    
    return base_prompt


def get_data_transformation_prompt(source_format: str, target_format: str, extra_instructions: str = "") -> str:
    """
    获取数据转换提示词。
    
    Args:
        source_format: 源数据格式，如'json'、'csv'、'table'等
        target_format: 目标数据格式
        extra_instructions: 额外指示
        
    Returns:
        数据转换提示词
    """
    prompt = f"""
    请将以下{source_format}格式的数据转换为{target_format}格式。
    
    转换时请确保：
    1. 保留所有必要的数据字段
    2. 根据需要调整数据结构
    3. 使用适当的格式约定
    4. 处理可能的特殊字符和边界情况
    
    转换结果应为有效的{target_format}格式，并且可以直接使用。
    """
    
    # 添加针对特定格式的额外指示
    format_specific_instructions = {
        "json-to-csv": "CSV应使用逗号分隔，并包括标题行。对包含逗号的字段使用引号包围。",
        "json-to-markdown": "Markdown表格应格式规范，第一行为标题，第二行为分隔符（如|---|---|）。",
        "json-to-html": "HTML表格应包含适当的标签（table, tr, th, td等），并使用有意义的类名便于样式设置。",
        "csv-to-json": "JSON应为数组格式，每行CSV对应一个JSON对象，字段名应使用第一行CSV的标题。",
    }
    
    format_key = f"{source_format}-to-{target_format}".lower()
    if format_key in format_specific_instructions:
        prompt += f"\n\n{format_specific_instructions[format_key]}"
    
    # 添加额外指示（如果有）
    if extra_instructions:
        prompt += f"\n\n{extra_instructions}"
    
    return prompt


def get_data_cleaning_prompt(data_type: str, cleaning_tasks: list = None) -> str:
    """
    获取数据清洗提示词。
    
    Args:
        data_type: 数据类型，如'text'、'table'、'list'等
        cleaning_tasks: 清洗任务列表，如['remove_duplicates', 'fix_missing_values']
        
    Returns:
        数据清洗提示词
    """
    if cleaning_tasks is None:
        cleaning_tasks = ["remove_duplicates", "fix_missing_values", "standardize_format"]
    
    task_descriptions = {
        "remove_duplicates": "删除重复项，保留一个有效实例",
        "fix_missing_values": "处理缺失值，使用合适的方法填充或标记",
        "standardize_format": "标准化格式，确保一致性",
        "correct_errors": "修正明显的错误和异常值",
        "normalize_text": "规范化文本，包括大小写、标点和空白",
        "remove_outliers": "识别并处理异常值",
    }
    
    # 构建任务描述
    tasks_text = "\n".join(f"- {task_descriptions.get(task, task)}" for task in cleaning_tasks)
    
    prompt = f"""
    请对以下{data_type}数据进行清洗处理，完成以下任务：
    
    {tasks_text}
    
    清洗后的数据应保持原始结构，但质量更高、更规范化。
    请提供有关清洗过程的详细说明，包括处理的问题和采取的方法。
    
    输出格式为JSON，包含以下字段：
    - cleaned_data: 清洗后的数据
    - cleaning_summary: 清洗摘要，包括处理的问题数量和类型
    - modifications: 进行的修改列表，包括原始值和修改后的值
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt 