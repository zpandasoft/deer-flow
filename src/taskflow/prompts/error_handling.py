# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
错误处理智能体提示词模板模块。

提供用于错误诊断、恢复建议和解决方案生成的提示词模板。
"""

from typing import Dict, Any, List, Optional

from src.taskflow.prompts.templates import get_json_output_instruction, format_bulleted_list


def get_error_handler_system_prompt() -> str:
    """
    获取错误处理智能体的默认系统提示词。
    
    Returns:
        系统提示词
    """
    return """
    你是一个专业的错误处理智能体，负责诊断执行过程中的异常情况，提供恢复建议和解决方案。
    
    你的主要任务是：
    1. 分析错误信息和上下文，准确诊断错误原因
    2. 评估错误的严重程度和影响范围
    3. 提供恢复策略和解决方案
    4. 推荐预防措施避免类似错误
    
    处理错误时，请保持分析的深入和系统性，从多个角度考虑可能的原因。
    提供的解决方案应该具体、可行，并考虑实施复杂度和潜在风险。
    """


def get_error_diagnosis_prompt() -> str:
    """
    获取错误诊断提示词。
    
    Returns:
        错误诊断提示词
    """
    prompt = """
    请基于以下错误信息和上下文，诊断错误的根本原因。
    
    诊断时请考虑以下可能的错误类型：
    • 输入数据问题（格式错误、缺失值、无效值等）
    • 环境配置问题（依赖缺失、版本不兼容等）
    • 资源限制问题（内存不足、超时等）
    • 权限问题（文件访问权限、API权限等）
    • 网络连接问题（超时、服务不可用等）
    • 代码逻辑问题（边界条件、算法错误等）
    • 并发问题（竞态条件、死锁等）
    
    输出格式为JSON，包含以下字段：
    - error_type: 错误类型
    - root_cause: 根本原因分析
    - contributing_factors: 相关因素列表
    - confidence: 诊断的置信度（0-100%）
    - evidence: 支持诊断的证据列表
    - alternative_causes: 其他可能的原因列表
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt


def get_recovery_strategy_prompt(error_type: str = None) -> str:
    """
    获取恢复策略提示词。
    
    Args:
        error_type: 错误类型，如果提供则生成针对特定类型的恢复策略
        
    Returns:
        恢复策略提示词
    """
    error_specific_instruction = ""
    if error_type:
        # 针对特定错误类型的额外指示
        error_type_instructions = {
            "data_error": "考虑数据验证、清洗和转换策略，以及如何处理异常数据。",
            "api_error": "考虑API重试策略、降级方案和替代服务选项。",
            "resource_error": "考虑资源优化、扩展和限流策略。",
            "permission_error": "考虑权限调整、最小权限原则和安全合规措施。",
            "timeout_error": "考虑超时处理、异步操作和性能优化措施。",
            "concurrency_error": "考虑锁机制、事务处理和并发控制策略。",
        }
        
        if error_type in error_type_instructions:
            error_specific_instruction = f"\n\n针对{error_type}类型的错误，{error_type_instructions[error_type]}"
    
    prompt = f"""
    请基于错误诊断结果，提供恢复策略和解决方案。{error_specific_instruction}
    
    提供恢复策略时，请考虑：
    1. 立即可执行的应急措施
    2. 短期解决方案
    3. 长期修复方案
    4. 相关风险和副作用
    
    输出格式为JSON，包含以下字段：
    - immediate_actions: 立即应急措施列表，包含步骤和预期效果
    - short_term_solutions: 短期解决方案列表，包含方法、时间估计和资源需求
    - long_term_fixes: 长期修复方案列表，包含方法、复杂度和收益
    - implementation_risks: 实施风险列表，包含风险描述和缓解措施
    - verification_steps: 验证解决方案有效性的步骤
    - fallback_options: 备选方案，如果主要解决方案失败
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt


def get_error_prevention_prompt() -> str:
    """
    获取错误预防提示词。
    
    Returns:
        错误预防提示词
    """
    prompt = """
    请基于已发生的错误和解决方案，提供预防类似错误的建议。
    
    考虑以下预防措施类型：
    • 代码改进（健壮性、错误处理、日志等）
    • 流程优化（审查、测试、部署等）
    • 监控增强（警报、指标、日志等）
    • 文档完善（使用指南、故障排除文档等）
    • 培训和最佳实践
    
    输出格式为JSON，包含以下字段：
    - code_improvements: 代码层面的改进建议列表
    - process_enhancements: 流程优化建议列表
    - monitoring_suggestions: 监控增强建议列表
    - documentation_updates: 文档完善建议列表
    - training_topics: 相关培训主题和最佳实践
    - priority_recommendations: 优先级最高的建议列表
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt


def get_error_impact_analysis_prompt() -> str:
    """
    获取错误影响分析提示词。
    
    Returns:
        错误影响分析提示词
    """
    prompt = """
    请基于错误信息和系统上下文，分析此错误的影响范围和严重程度。
    
    分析时请考虑以下方面：
    • 用户体验影响（有多少用户受影响，体验受损程度）
    • 数据影响（数据丢失、损坏或不一致的风险）
    • 系统稳定性影响（是否影响整体系统可用性）
    • 业务影响（对业务流程和目标的影响）
    • 安全影响（是否存在安全风险或漏洞）
    
    输出格式为JSON，包含以下字段：
    - severity: 严重程度评级（低、中、高、致命）
    - scope: 影响范围描述
    - user_impact: 用户影响评估，包含影响用户数和体验影响
    - data_impact: 数据影响评估
    - system_impact: 系统稳定性影响
    - business_impact: 业务影响评估
    - security_implications: 安全影响评估
    - mttr_estimate: 修复时间估计（Mean Time To Recover）
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt


def get_troubleshooting_guide_prompt(error_category: str) -> str:
    """
    获取故障排除指南提示词。
    
    Args:
        error_category: 错误类别，如'api'、'database'、'network'等
        
    Returns:
        故障排除指南提示词
    """
    prompt = f"""
    请创建一个详细的{error_category}错误故障排除指南，帮助用户诊断和解决相关问题。
    
    指南应包含：
    1. 常见错误症状和错误消息
    2. 诊断步骤和检查点
    3. 针对不同原因的解决方法
    4. 验证修复的方法
    
    输出格式为JSON，包含以下字段：
    - common_symptoms: 常见症状和错误消息列表
    - diagnostic_steps: 诊断步骤列表，包含每个步骤的描述和预期结果
    - solutions: 解决方案列表，针对不同的诊断结果
    - verification_methods: 验证问题解决的方法
    - additional_resources: 额外资源和参考链接
    - troubleshooting_flowchart: 故障排除流程图（文本描述）
    """
    
    # 添加JSON输出指示
    prompt += f"\n\n{get_json_output_instruction()}"
    
    return prompt 