# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
质量评估智能体提示词模板模块。

提供用于评估任务执行质量和生成改进建议的提示词模板。
"""

from typing import Dict, Any, List, Optional

from src.taskflow.prompts.templates import get_json_output_instruction, format_bulleted_list


def get_quality_evaluator_system_prompt() -> str:
    """
    获取质量评估智能体的默认系统提示词。
    
    Returns:
        系统提示词
    """
    return """
    你是一个专业的质量评估智能体，负责评估任务执行结果的质量并提供改进建议。
    
    你的主要任务是：
    1. 基于多维度标准评估内容质量
    2. 识别内容中的错误、不一致和缺失
    3. 提供具体的改进建议
    4. 给出整体评分和评价
    
    评估时，请保持客观、公正，并提供详细的分析依据。
    关注内容的准确性、完整性、一致性、清晰度和实用性等方面。
    """


def get_content_evaluation_prompt(content_type: str, evaluation_criteria: Optional[List[str]] = None) -> str:
    """
    获取内容评估提示词。
    
    Args:
        content_type: 内容类型，如'research_report'、'data_analysis'、'summary'等
        evaluation_criteria: 评估标准列表，如果为None则使用默认标准
        
    Returns:
        内容评估提示词
    """
    # 默认评估标准
    default_criteria = {
        "research_report": [
            "信息准确性", "研究深度", "论点支持", "结构组织", "信息来源可靠性", 
            "结论合理性", "写作质量", "格式规范性"
        ],
        "data_analysis": [
            "数据准确性", "分析方法适当性", "结论合理性", "可视化清晰度", 
            "统计严谨性", "解释清晰度", "局限性讨论"
        ],
        "summary": [
            "信息完整性", "关键点覆盖", "简洁性", "准确性", "中立性"
        ],
        "code": [
            "功能正确性", "代码效率", "可读性", "可维护性", "错误处理", 
            "安全性", "文档完整性", "测试覆盖"
        ],
        "translation": [
            "准确性", "流畅性", "文化适应性", "术语一致性", "格式保留"
        ],
    }
    
    # 如果未提供评估标准，则使用默认标准或通用标准
    if evaluation_criteria is None:
        evaluation_criteria = default_criteria.get(
            content_type, 
            ["准确性", "完整性", "一致性", "清晰度", "实用性", "格式规范性"]
        )
    
    # 构建评估标准列表
    criteria_text = format_bulleted_list(evaluation_criteria)
    
    prompt = f"""
    请对以下{content_type}进行质量评估，基于以下标准：
    
    {criteria_text}
    
    对每个标准，请给出1-10的评分（10为最高），并提供具体评价和改进建议。
    同时，请提供整体评分和总体评价。
    
    输出格式为JSON，包含以下字段：
    - criteria_scores: 各项标准的评分和评价
    - overall_score: 整体评分（1-10）
    - strengths: 内容优点列表
    - weaknesses: 内容缺点列表
    - improvement_suggestions: 改进建议列表
    - conclusion: 总体评价
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt


def get_comparison_evaluation_prompt(num_items: int, comparison_aspects: Optional[List[str]] = None) -> str:
    """
    获取比较评估提示词。
    
    Args:
        num_items: 比较项数量
        comparison_aspects: 比较方面列表，如果为None则使用默认方面
        
    Returns:
        比较评估提示词
    """
    # 默认比较方面
    if comparison_aspects is None:
        comparison_aspects = ["准确性", "完整性", "清晰度", "实用性", "创新性"]
    
    # 构建比较方面列表
    aspects_text = format_bulleted_list(comparison_aspects)
    
    prompt = f"""
    请对以下{num_items}个结果进行比较评估，基于以下方面：
    
    {aspects_text}
    
    对每个方面，请为每个结果给出1-10的评分（10为最高），并提供比较分析。
    同时，确定总体最佳结果，并说明理由。
    
    输出格式为JSON，包含以下字段：
    - aspect_scores: 各方面的评分和比较，每个方面包含所有结果的得分
    - overall_ranking: 结果的总体排名，从最佳到最差
    - best_result: 最佳结果的编号（1到{num_items}）
    - comparison_summary: 比较总结，包括各结果的优缺点
    - recommendation: 推荐使用哪个结果，以及原因
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt


def get_error_detection_prompt() -> str:
    """
    获取错误检测提示词。
    
    Returns:
        错误检测提示词
    """
    prompt = """
    请对以下内容进行彻底的错误检测，包括：
    
    • 事实错误
    • 逻辑错误
    • 数据不一致
    • 计算错误
    • 引用错误
    • 格式问题
    • 拼写和语法错误
    
    对于每个发现的错误，请提供：
    - 错误位置
    - 错误描述
    - 建议修正
    - 错误严重程度（轻微、中等、严重）
    
    输出格式为JSON，包含以下字段：
    - errors: 发现的错误列表，每个错误包含类型、位置、描述、建议修正和严重程度
    - error_count: 错误总数
    - severity_summary: 各严重程度错误的数量
    - overall_quality: 内容整体质量评估（高、中、低）
    - highest_priority_fixes: 最需要优先修复的错误列表
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt


def get_completeness_check_prompt(required_elements: List[str]) -> str:
    """
    获取完整性检查提示词。
    
    Args:
        required_elements: 必需元素列表
        
    Returns:
        完整性检查提示词
    """
    # 构建必需元素列表
    elements_text = format_bulleted_list(required_elements)
    
    prompt = f"""
    请检查以下内容的完整性，确保包含所有必需元素：
    
    {elements_text}
    
    对于每个必需元素，请确定：
    - 是否存在
    - 是否完整
    - 质量如何
    - 是否需要改进
    
    输出格式为JSON，包含以下字段：
    - elements_check: 每个元素的检查结果
    - missing_elements: 缺失元素列表
    - incomplete_elements: 不完整元素列表
    - completeness_score: 完整性评分（0-100%）
    - suggestions: 改进建议列表
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt 