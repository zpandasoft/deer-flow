# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
质量评估智能体模块。

负责评估任务执行质量，检测错误和不一致性，并提供改进建议。
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from langchain.schema import HumanMessage, SystemMessage
from langchain.schema.runnable import Runnable

from src.taskflow.agents.base import LLMAgent
from src.taskflow.exceptions import AgentError
from src.taskflow.prompts.quality_evaluation import (
    get_quality_evaluator_system_prompt,
    get_content_evaluation_prompt,
    get_comparison_evaluation_prompt,
    get_error_detection_prompt,
    get_completeness_check_prompt
)
from src.taskflow.utils.logger import log_execution_time

# 获取日志记录器
logger = logging.getLogger(__name__)


class QualityEvaluatorAgent(LLMAgent[Dict[str, Any], Dict[str, Any]]):
    """
    质量评估智能体。
    
    评估任务执行质量，检测错误和不一致性，并提供改进建议。
    """
    
    def __init__(
        self,
        llm: Runnable,
        name: str = "quality_evaluator",
        description: str = "评估任务执行质量，检测错误和不一致性，并提供改进建议",
        metadata: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> None:
        """
        初始化质量评估智能体。
        
        Args:
            llm: LLM可运行实例
            name: 智能体名称
            description: 智能体描述
            metadata: 智能体元数据
            system_prompt: 系统提示词，如果为None则使用默认提示词
        """
        # 如果未提供系统提示词，使用默认提示词
        if system_prompt is None:
            system_prompt = get_quality_evaluator_system_prompt()
        
        super().__init__(name, llm, description, metadata, system_prompt)
    
    @log_execution_time(logger)
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行质量评估智能体。
        
        Args:
            input_data: 输入数据，必须包含"content"字段和"evaluation_type"字段
            
        Returns:
            评估结果
            
        Raises:
            AgentError: 如果评估失败
        """
        # 验证输入
        self._validate_input(input_data)
        
        content = input_data["content"]
        evaluation_type = input_data["evaluation_type"]
        
        logger.info(f"开始评估内容质量，评估类型: {evaluation_type}")
        
        # 根据评估类型获取提示词
        prompt_text, formatted_content = self._get_prompt_and_format_content(evaluation_type, input_data)
        
        # 构建消息
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"{prompt_text}\n\n{formatted_content}")
        ]
        
        # 调用LLM
        try:
            response = await self._call_llm(messages)
            logger.debug(f"LLM原始响应: {response}")
            
            # 解析JSON响应
            result = self._parse_response(response)
            
            # 添加评估元数据
            result["meta"] = {
                "evaluation_type": evaluation_type,
                "evaluated_by": self.name,
                "evaluation_parameters": input_data.get("parameters", {})
            }
            
            return result
        except Exception as e:
            error_msg = f"评估内容质量时出错: {str(e)}"
            logger.exception(error_msg)
            raise AgentError(error_msg) from e
    
    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """
        验证输入数据。
        
        Args:
            input_data: 输入数据
            
        Raises:
            AgentError: 如果输入数据无效
        """
        if "content" not in input_data:
            raise AgentError("输入数据必须包含'content'字段")
        
        if "evaluation_type" not in input_data:
            raise AgentError("输入数据必须包含'evaluation_type'字段")
        
        # 检查评估类型是否支持
        evaluation_type = input_data["evaluation_type"]
        supported_evaluation_types = [
            "content_evaluation", "comparison_evaluation", 
            "error_detection", "completeness_check"
        ]
        
        if evaluation_type not in supported_evaluation_types:
            raise AgentError(f"不支持的评估类型: {evaluation_type}，支持的评估类型: {supported_evaluation_types}")
        
        # 针对比较评估的额外检查
        if evaluation_type == "comparison_evaluation" and not isinstance(input_data["content"], list):
            raise AgentError("比较评估的'content'字段必须是列表")
    
    def _get_prompt_and_format_content(
        self, 
        evaluation_type: str, 
        input_data: Dict[str, Any]
    ) -> tuple[str, str]:
        """
        根据评估类型获取提示词和格式化内容。
        
        Args:
            evaluation_type: 评估类型
            input_data: 输入数据
            
        Returns:
            提示词和格式化内容的元组
        """
        content = input_data["content"]
        
        # 内容评估
        if evaluation_type == "content_evaluation":
            content_type = input_data.get("content_type", "text")
            evaluation_criteria = input_data.get("evaluation_criteria")
            
            prompt = get_content_evaluation_prompt(content_type, evaluation_criteria)
            return prompt, content
        
        # 比较评估
        elif evaluation_type == "comparison_evaluation":
            # 确保内容是列表
            if not isinstance(content, list):
                raise AgentError("比较评估的'content'字段必须是列表")
            
            num_items = len(content)
            comparison_aspects = input_data.get("comparison_aspects")
            
            prompt = get_comparison_evaluation_prompt(num_items, comparison_aspects)
            
            # 格式化比较内容
            formatted_content = ""
            for i, item in enumerate(content):
                formatted_content += f"项目 {i+1}:\n{item}\n\n"
            
            return prompt, formatted_content
        
        # 错误检测
        elif evaluation_type == "error_detection":
            prompt = get_error_detection_prompt()
            return prompt, content
        
        # 完整性检查
        elif evaluation_type == "completeness_check":
            required_elements = input_data.get("required_elements")
            if not required_elements:
                raise AgentError("完整性检查需要'required_elements'字段")
            
            prompt = get_completeness_check_prompt(required_elements)
            return prompt, content
        
        # 默认情况（不应该到达这里，因为_validate_input已经检查了评估类型）
        raise AgentError(f"未知的评估类型: {evaluation_type}")
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """
        解析LLM响应。
        
        Args:
            response: LLM响应文本
            
        Returns:
            解析后的响应
            
        Raises:
            AgentError: 如果无法解析响应
        """
        try:
            # 尝试直接解析JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试从文本中提取JSON
            try:
                # 寻找JSON对象的开始和结束
                start_idx = response.find('{')
                end_idx = response.rfind('}') + 1
                
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response[start_idx:end_idx]
                    return json.loads(json_str)
                else:
                    raise AgentError("无法从响应中提取JSON")
            except Exception as e:
                error_msg = f"解析响应失败: {str(e)}\n原始响应: {response}"
                logger.error(error_msg)
                raise AgentError(error_msg) from e
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        获取智能体可用工具列表。
        
        Returns:
            工具列表
        """
        # 质量评估智能体当前不使用外部工具
        return []
    
    async def evaluate_content(
        self, 
        content: str, 
        content_type: str, 
        evaluation_criteria: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        评估内容质量。
        
        Args:
            content: 要评估的内容
            content_type: 内容类型（如'research_report'、'data_analysis'等）
            evaluation_criteria: 评估标准列表，如果为None则使用默认标准
            
        Returns:
            评估结果
        """
        input_data = {
            "content": content,
            "evaluation_type": "content_evaluation",
            "content_type": content_type,
            "evaluation_criteria": evaluation_criteria
        }
        
        return await self.run(input_data)
    
    async def compare_results(
        self, 
        results: List[str], 
        comparison_aspects: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        比较多个结果的质量。
        
        Args:
            results: 要比较的结果列表
            comparison_aspects: 比较方面列表，如果为None则使用默认方面
            
        Returns:
            比较结果
        """
        input_data = {
            "content": results,
            "evaluation_type": "comparison_evaluation",
            "comparison_aspects": comparison_aspects
        }
        
        return await self.run(input_data)
    
    async def detect_errors(self, content: str) -> Dict[str, Any]:
        """
        检测内容中的错误。
        
        Args:
            content: 要检测的内容
            
        Returns:
            错误检测结果
        """
        input_data = {
            "content": content,
            "evaluation_type": "error_detection"
        }
        
        return await self.run(input_data)
    
    async def check_completeness(
        self, 
        content: str, 
        required_elements: List[str]
    ) -> Dict[str, Any]:
        """
        检查内容的完整性。
        
        Args:
            content: 要检查的内容
            required_elements: 必需元素列表
            
        Returns:
            完整性检查结果
        """
        input_data = {
            "content": content,
            "evaluation_type": "completeness_check",
            "required_elements": required_elements
        }
        
        return await self.run(input_data) 