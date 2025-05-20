# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
错误处理智能体模块。

负责诊断执行过程中的异常情况，提供恢复建议和解决方案。
"""

import json
import logging
import traceback
from typing import Any, Dict, List, Optional, Union

from langchain.schema import HumanMessage, SystemMessage
from langchain.schema.runnable import Runnable

from src.taskflow.agents.base import LLMAgent
from src.taskflow.exceptions import AgentError
from src.taskflow.prompts.error_handling import (
    get_error_handler_system_prompt,
    get_error_diagnosis_prompt,
    get_recovery_strategy_prompt,
    get_error_prevention_prompt,
    get_error_impact_analysis_prompt,
    get_troubleshooting_guide_prompt
)
from src.taskflow.utils.logger import log_execution_time

# 获取日志记录器
logger = logging.getLogger(__name__)


class ErrorHandlerAgent(LLMAgent[Dict[str, Any], Dict[str, Any]]):
    """
    错误处理智能体。
    
    诊断执行过程中的异常情况，提供恢复建议和解决方案。
    """
    
    def __init__(
        self,
        llm: Runnable,
        name: str = "error_handler",
        description: str = "诊断执行过程中的异常情况，提供恢复建议和解决方案",
        metadata: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> None:
        """
        初始化错误处理智能体。
        
        Args:
            llm: LLM可运行实例
            name: 智能体名称
            description: 智能体描述
            metadata: 智能体元数据
            system_prompt: 系统提示词，如果为None则使用默认提示词
        """
        # 如果未提供系统提示词，使用默认提示词
        if system_prompt is None:
            system_prompt = get_error_handler_system_prompt()
        
        super().__init__(name, llm, description, metadata, system_prompt)
    
    @log_execution_time(logger)
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行错误处理智能体。
        
        Args:
            input_data: 输入数据，必须包含"error_info"字段和"handling_type"字段
            
        Returns:
            错误处理结果
            
        Raises:
            AgentError: 如果错误处理失败
        """
        # 验证输入
        self._validate_input(input_data)
        
        error_info = input_data["error_info"]
        handling_type = input_data["handling_type"]
        context = input_data.get("context", {})
        
        logger.info(f"开始处理错误，处理类型: {handling_type}")
        
        # 根据处理类型获取提示词
        prompt_text, formatted_error_info = self._get_prompt_and_format_error(handling_type, error_info, context)
        
        # 构建消息
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"{prompt_text}\n\n{formatted_error_info}")
        ]
        
        # 调用LLM
        try:
            response = await self._call_llm(messages)
            logger.debug(f"LLM原始响应: {response}")
            
            # 解析JSON响应
            result = self._parse_response(response)
            
            # 添加处理元数据
            result["meta"] = {
                "handling_type": handling_type,
                "handled_by": self.name,
                "error_type": self._extract_error_type(error_info),
                "handling_parameters": input_data.get("parameters", {})
            }
            
            return result
        except Exception as e:
            error_msg = f"处理错误时出错: {str(e)}"
            logger.exception(error_msg)
            # 当错误处理本身失败时，返回一个简单的错误报告而不是抛出异常
            return {
                "error_handling_failed": True,
                "original_error": self._format_error_for_output(error_info),
                "handling_error": str(e),
                "meta": {
                    "handling_type": handling_type,
                    "handled_by": self.name,
                    "error_type": self._extract_error_type(error_info),
                }
            }
    
    def _validate_input(self, input_data: Dict[str, Any]) -> None:
        """
        验证输入数据。
        
        Args:
            input_data: 输入数据
            
        Raises:
            AgentError: 如果输入数据无效
        """
        if "error_info" not in input_data:
            raise AgentError("输入数据必须包含'error_info'字段")
        
        if "handling_type" not in input_data:
            raise AgentError("输入数据必须包含'handling_type'字段")
        
        # 检查处理类型是否支持
        handling_type = input_data["handling_type"]
        supported_handling_types = [
            "diagnosis", "recovery", "prevention", 
            "impact_analysis", "troubleshooting_guide"
        ]
        
        if handling_type not in supported_handling_types:
            raise AgentError(f"不支持的处理类型: {handling_type}，支持的处理类型: {supported_handling_types}")
    
    def _extract_error_type(self, error_info: Any) -> str:
        """
        从错误信息中提取错误类型。
        
        Args:
            error_info: 错误信息
            
        Returns:
            错误类型
        """
        if isinstance(error_info, dict) and "error_type" in error_info:
            return error_info["error_type"]
        elif isinstance(error_info, dict) and "exception" in error_info:
            exception = error_info["exception"]
            if isinstance(exception, str) and ":" in exception:
                return exception.split(":", 1)[0].strip()
            return str(exception)
        elif isinstance(error_info, Exception):
            return error_info.__class__.__name__
        elif isinstance(error_info, str):
            # 尝试从错误消息中提取类型
            if ":" in error_info:
                return error_info.split(":", 1)[0].strip()
        
        return "UnknownError"
    
    def _format_error_for_output(self, error_info: Any) -> Dict[str, Any]:
        """
        格式化错误信息用于输出。
        
        Args:
            error_info: 错误信息
            
        Returns:
            格式化的错误信息
        """
        if isinstance(error_info, dict):
            return error_info
        elif isinstance(error_info, Exception):
            return {
                "error_type": error_info.__class__.__name__,
                "error_message": str(error_info),
                "traceback": traceback.format_exception(type(error_info), error_info, error_info.__traceback__)
            }
        elif isinstance(error_info, str):
            return {
                "error_message": error_info,
                "error_type": self._extract_error_type(error_info)
            }
        else:
            return {
                "error_message": str(error_info),
                "error_type": "UnknownError"
            }
    
    def _get_prompt_and_format_error(
        self, 
        handling_type: str, 
        error_info: Any, 
        context: Dict[str, Any]
    ) -> tuple[str, str]:
        """
        根据处理类型获取提示词和格式化错误信息。
        
        Args:
            handling_type: 处理类型
            error_info: 错误信息
            context: 上下文信息
            
        Returns:
            提示词和格式化错误信息的元组
        """
        # 格式化错误信息
        formatted_error_info = self._format_error_info(error_info, context)
        
        # 错误诊断
        if handling_type == "diagnosis":
            prompt = get_error_diagnosis_prompt()
            return prompt, formatted_error_info
        
        # 恢复策略
        elif handling_type == "recovery":
            error_type = self._extract_error_type(error_info)
            prompt = get_recovery_strategy_prompt(error_type)
            return prompt, formatted_error_info
        
        # 错误预防
        elif handling_type == "prevention":
            prompt = get_error_prevention_prompt()
            return prompt, formatted_error_info
        
        # 影响分析
        elif handling_type == "impact_analysis":
            prompt = get_error_impact_analysis_prompt()
            return prompt, formatted_error_info
        
        # 故障排除指南
        elif handling_type == "troubleshooting_guide":
            # 确定错误类别
            error_category = context.get("error_category", "general")
            prompt = get_troubleshooting_guide_prompt(error_category)
            return prompt, formatted_error_info
        
        # 默认情况（不应该到达这里，因为_validate_input已经检查了处理类型）
        raise AgentError(f"未知的处理类型: {handling_type}")
    
    def _format_error_info(self, error_info: Any, context: Dict[str, Any]) -> str:
        """
        格式化错误信息。
        
        Args:
            error_info: 错误信息
            context: 上下文信息
            
        Returns:
            格式化的错误信息字符串
        """
        formatted_error = "错误信息:\n"
        
        # 处理不同类型的错误信息
        if isinstance(error_info, dict):
            try:
                formatted_error += json.dumps(error_info, ensure_ascii=False, indent=2)
            except:
                # 如果JSON序列化失败，则使用字符串表示
                formatted_error += str(error_info)
        elif isinstance(error_info, Exception):
            formatted_error += f"错误类型: {error_info.__class__.__name__}\n"
            formatted_error += f"错误消息: {str(error_info)}\n"
            formatted_error += f"堆栈跟踪:\n{''.join(traceback.format_exception(type(error_info), error_info, error_info.__traceback__))}"
        else:
            formatted_error += str(error_info)
        
        # 添加上下文信息
        if context:
            formatted_error += "\n\n上下文信息:\n"
            try:
                formatted_error += json.dumps(context, ensure_ascii=False, indent=2)
            except:
                formatted_error += str(context)
        
        return formatted_error
    
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
                    # 如果找不到JSON，则将响应作为文本返回
                    return {"analysis_text": response}
            except Exception as e:
                logger.warning(f"解析响应失败: {str(e)}")
                # 不抛出异常，而是将原始响应作为文本返回
                return {"analysis_text": response}
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        获取智能体可用工具列表。
        
        Returns:
            工具列表
        """
        # 错误处理智能体当前不使用外部工具
        return []
    
    async def diagnose_error(
        self,
        error_info: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        诊断错误。
        
        Args:
            error_info: 错误信息
            context: 错误上下文
            
        Returns:
            诊断结果
        """
        input_data = {
            "error_info": error_info,
            "handling_type": "diagnosis",
            "context": context or {}
        }
        
        return await self.run(input_data)
    
    async def get_recovery_strategy(
        self,
        error_info: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        获取恢复策略。
        
        Args:
            error_info: 错误信息
            context: 错误上下文
            
        Returns:
            恢复策略
        """
        input_data = {
            "error_info": error_info,
            "handling_type": "recovery",
            "context": context or {}
        }
        
        return await self.run(input_data)
    
    async def get_prevention_recommendations(
        self,
        error_info: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        获取错误预防建议。
        
        Args:
            error_info: 错误信息
            context: 错误上下文
            
        Returns:
            预防建议
        """
        input_data = {
            "error_info": error_info,
            "handling_type": "prevention",
            "context": context or {}
        }
        
        return await self.run(input_data)
    
    async def analyze_error_impact(
        self,
        error_info: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        分析错误影响。
        
        Args:
            error_info: 错误信息
            context: 错误上下文
            
        Returns:
            影响分析结果
        """
        input_data = {
            "error_info": error_info,
            "handling_type": "impact_analysis",
            "context": context or {}
        }
        
        return await self.run(input_data)
    
    async def create_troubleshooting_guide(
        self,
        error_category: str,
        error_examples: List[Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建故障排除指南。
        
        Args:
            error_category: 错误类别
            error_examples: 错误示例列表
            context: 额外上下文
            
        Returns:
            故障排除指南
        """
        if context is None:
            context = {}
        
        context.update({"error_category": error_category})
        
        input_data = {
            "error_info": {"examples": error_examples},
            "handling_type": "troubleshooting_guide",
            "context": context
        }
        
        return await self.run(input_data) 