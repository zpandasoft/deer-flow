# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
合成智能体提示词模板模块。

提供用于汇总多任务结果、生成综合报告和结论的提示词模板。
"""

from typing import Dict, Any, List, Optional

from src.taskflow.prompts.templates import get_json_output_instruction, format_bulleted_list


def get_synthesis_system_prompt() -> str:
    """
    获取合成智能体的默认系统提示词。
    
    Returns:
        系统提示词
    """
    return """
    你是一个专业的合成智能体，负责汇总多个任务或步骤的结果，生成综合性报告和结论。
    
    你的主要任务是：
    1. 整合和汇总多个数据源或结果
    2. 识别共同点、差异点和趋势
    3. 合成一致的、全面的分析和结论
    4. 生成结构清晰、重点突出的报告
    
    合成时，请注意保持客观和准确，确保内容的一致性和完整性。
    避免重复信息，突出关键发现，并提供有见地的分析。
    """


def get_report_synthesis_prompt(report_type: str, sections: Optional[List[str]] = None) -> str:
    """
    获取报告合成提示词。
    
    Args:
        report_type: 报告类型，如'research'、'market_analysis'、'technical'等
        sections: 报告章节列表，如果为None则使用默认章节
        
    Returns:
        报告合成提示词
    """
    # 默认报告章节
    default_sections = {
        "research": [
            "摘要", "背景介绍", "研究目标", "方法论", "关键发现", 
            "分析讨论", "结论", "建议", "参考资料"
        ],
        "market_analysis": [
            "摘要", "市场概况", "需求分析", "竞争分析", "SWOT分析", 
            "市场趋势", "机会与挑战", "建议策略", "附录"
        ],
        "technical": [
            "摘要", "背景", "技术需求", "设计方案", "实现细节", 
            "测试结果", "性能分析", "结论与建议", "参考资料"
        ],
        "business": [
            "执行摘要", "公司介绍", "市场分析", "产品/服务", "营销策略", 
            "财务分析", "风险评估", "实施计划", "结论"
        ],
    }
    
    # 如果未提供章节，则使用默认章节或通用章节
    if sections is None:
        sections = default_sections.get(
            report_type, 
            ["摘要", "介绍", "方法", "结果", "讨论", "结论", "参考资料"]
        )
    
    # 构建章节列表
    sections_text = format_bulleted_list(sections)
    
    prompt = f"""
    请基于以下多个任务结果，合成一份完整的{report_type}报告，包含以下章节：
    
    {sections_text}
    
    合成时请注意：
    1. 确保各章节内容之间的一致性和连贯性
    2. 识别并整合不同任务结果中的关键信息
    3. 解决可能存在的冲突或矛盾
    4. 适当引用原始数据和信息源
    5. 提供清晰的结论和建议
    
    报告应具有专业性、全面性和洞察力，适合目标受众阅读。
    """
    
    return prompt


def get_findings_synthesis_prompt() -> str:
    """
    获取发现合成提示词。
    
    Returns:
        发现合成提示词
    """
    prompt = """
    请基于以下多个研究或分析任务的结果，合成关键发现和见解。
    
    合成时请：
    1. 识别各任务结果中的核心发现
    2. 寻找跨任务的共同模式、趋势或主题
    3. 突出具有重要意义的差异或矛盾
    4. 提供综合性解释和见解
    
    输出格式为JSON，包含以下字段：
    - key_findings: 主要发现列表，每个发现包含描述和支持证据
    - patterns: 识别的模式或趋势列表
    - contradictions: 发现的矛盾或不一致列表
    - implications: 这些发现的意义和影响
    - next_steps: 建议的后续步骤或研究方向
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt


def get_comparative_synthesis_prompt(comparison_dimensions: Optional[List[str]] = None) -> str:
    """
    获取比较合成提示词。
    
    Args:
        comparison_dimensions: 比较维度列表，如果为None则使用默认维度
        
    Returns:
        比较合成提示词
    """
    # 默认比较维度
    if comparison_dimensions is None:
        comparison_dimensions = ["优点", "缺点", "适用场景", "成本效益", "实施难度"]
    
    # 构建比较维度列表
    dimensions_text = format_bulleted_list(comparison_dimensions)
    
    prompt = f"""
    请基于以下多个方案或选项的分析结果，进行综合比较，比较维度包括：
    
    {dimensions_text}
    
    比较合成时请：
    1. 在每个维度上客观比较各方案
    2. 识别各方案的相对优势和劣势
    3. 确定适合不同场景的最佳方案
    4. 提供选择建议和决策依据
    
    输出格式为JSON，包含以下字段：
    - dimension_comparisons: 各维度的详细比较
    - strengths_weaknesses: 各方案的主要优缺点
    - best_fit_scenarios: 各方案最适合的场景
    - recommendation: 综合建议和推荐方案
    - decision_matrix: 决策矩阵，评分各方案在各维度的表现
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt


def get_timeline_synthesis_prompt() -> str:
    """
    获取时间线合成提示词。
    
    Returns:
        时间线合成提示词
    """
    prompt = """
    请基于以下多个事件、活动或发展的信息，合成一个连贯的时间线。
    
    合成时请：
    1. 确保事件的时间顺序准确
    2. 识别关键节点和转折点
    3. 建立事件之间的因果关系
    4. 提供每个时期的主要特征或主题
    
    输出格式为JSON，包含以下字段：
    - timeline: 时间线条目列表，每个条目包含日期、事件描述和重要性
    - key_periods: 关键时期列表，每个时期包含起止时间、特征和重要事件
    - turning_points: 转折点列表，包含时间、描述和影响
    - cause_effect_relationships: 主要因果关系列表
    - overall_narrative: 整体叙述，描述时间线的主要发展脉络
    - visualizations: 推荐的可视化方式，如何最佳展示此时间线
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt


def get_solution_synthesis_prompt() -> str:
    """
    获取解决方案合成提示词。
    
    Returns:
        解决方案合成提示词
    """
    prompt = """
    请基于以下多个分析和建议，合成一个全面的解决方案。
    
    合成时请：
    1. 整合各分析中的有效建议和方法
    2. 确保解决方案的各部分相互协调一致
    3. 解决潜在的实施挑战和风险
    4. 提供清晰的实施步骤和时间表
    
    输出格式为JSON，包含以下字段：
    - solution_overview: 解决方案概述
    - key_components: 主要组成部分列表，每个部分包含描述、目标和方法
    - implementation_steps: 实施步骤列表，包含顺序、时间估计和资源需求
    - risk_mitigation: 风险管理策略，包含潜在风险和应对措施
    - success_metrics: 成功指标列表，用于评估解决方案的有效性
    - resources_required: 所需资源列表，包含人力、技术和财务资源
    - timeline: 实施时间表，包含主要里程碑
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt 