# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
合成智能体模块。

负责汇总多任务结果，生成综合报告和结论，确保内容的一致性和完整性。
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from langchain.schema import HumanMessage, SystemMessage
from langchain.schema.runnable import Runnable

from src.taskflow.agents.base import LLMAgent
from src.taskflow.exceptions import AgentError
from src.taskflow.prompts.synthesis import (
    get_synthesis_system_prompt,
    get_report_synthesis_prompt,
    get_findings_synthesis_prompt,
    get_comparative_synthesis_prompt,
    get_timeline_synthesis_prompt,
    get_solution_synthesis_prompt
)
from src.taskflow.utils.logger import log_execution_time

# 获取日志记录器
logger = logging.getLogger(__name__)


class SynthesisAgent(LLMAgent[Dict[str, Any], Dict[str, Any]]):
    """
    合成智能体。
    
    汇总多任务结果，生成综合报告和结论，确保内容的一致性和完整性。
    """
    
    def __init__(
        self,
        llm: Runnable,
        name: str = "synthesis_agent",
        description: str = "汇总多任务结果，生成综合报告和结论，确保内容的一致性和完整性",
        metadata: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> None:
        """
        初始化合成智能体。
        
        Args:
            llm: LLM可运行实例
            name: 智能体名称
            description: 智能体描述
            metadata: 智能体元数据
            system_prompt: 系统提示词，如果为None则使用默认提示词
        """
        # 如果未提供系统提示词，使用默认提示词
        if system_prompt is None:
            system_prompt = get_synthesis_system_prompt()
        
        super().__init__(name, llm, description, metadata, system_prompt)
    
    @log_execution_time(logger)
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行合成智能体。
        
        Args:
            input_data: 输入数据，必须包含"results"字段和"synthesis_type"字段
            
        Returns:
            合成结果
            
        Raises:
            AgentError: 如果合成失败
        """
        # 验证输入
        self._validate_input(input_data)
        
        results = input_data["results"]
        synthesis_type = input_data["synthesis_type"]
        
        logger.info(f"开始合成结果，合成类型: {synthesis_type}")
        
        # 根据合成类型获取提示词
        prompt_text, formatted_results = self._get_prompt_and_format_results(synthesis_type, input_data)
        
        # 构建消息
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"{prompt_text}\n\n{formatted_results}")
        ]
        
        # 调用LLM
        try:
            response = await self._call_llm(messages)
            logger.debug(f"LLM原始响应: {response}")
            
            # 视合成类型处理响应
            result = self._process_response(response, synthesis_type)
            
            # 添加合成元数据
            result["meta"] = {
                "synthesis_type": synthesis_type,
                "synthesized_by": self.name,
                "synthesis_parameters": input_data.get("parameters", {})
            }
            
            return result
        except Exception as e:
            error_msg = f"合成结果时出错: {str(e)}"
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
        if "results" not in input_data:
            raise AgentError("输入数据必须包含'results'字段")
        
        if "synthesis_type" not in input_data:
            raise AgentError("输入数据必须包含'synthesis_type'字段")
        
        # 检查合成类型是否支持
        synthesis_type = input_data["synthesis_type"]
        supported_synthesis_types = [
            "report_synthesis", "findings_synthesis", 
            "comparative_synthesis", "timeline_synthesis", 
            "solution_synthesis"
        ]
        
        if synthesis_type not in supported_synthesis_types:
            raise AgentError(f"不支持的合成类型: {synthesis_type}，支持的合成类型: {supported_synthesis_types}")
        
        # 确保results是列表或字典
        results = input_data["results"]
        if not isinstance(results, (list, dict)):
            raise AgentError("'results'字段必须是列表或字典")
    
    def _get_prompt_and_format_results(
        self, 
        synthesis_type: str, 
        input_data: Dict[str, Any]
    ) -> tuple[str, str]:
        """
        根据合成类型获取提示词和格式化结果。
        
        Args:
            synthesis_type: 合成类型
            input_data: 输入数据
            
        Returns:
            提示词和格式化结果的元组
        """
        results = input_data["results"]
        
        # 报告合成
        if synthesis_type == "report_synthesis":
            report_type = input_data.get("report_type", "research")
            sections = input_data.get("sections")
            
            prompt = get_report_synthesis_prompt(report_type, sections)
            
            # 格式化结果
            if isinstance(results, list):
                formatted_results = self._format_list_results(results)
            else:  # dict
                formatted_results = self._format_dict_results(results)
            
            return prompt, formatted_results
        
        # 发现合成
        elif synthesis_type == "findings_synthesis":
            prompt = get_findings_synthesis_prompt()
            
            # 格式化结果
            if isinstance(results, list):
                formatted_results = self._format_list_results(results)
            else:  # dict
                formatted_results = self._format_dict_results(results)
            
            return prompt, formatted_results
        
        # 比较合成
        elif synthesis_type == "comparative_synthesis":
            comparison_dimensions = input_data.get("comparison_dimensions")
            
            prompt = get_comparative_synthesis_prompt(comparison_dimensions)
            
            # 格式化结果
            if isinstance(results, list):
                formatted_results = self._format_list_results(results)
            else:  # dict
                formatted_results = self._format_dict_results(results)
            
            return prompt, formatted_results
        
        # 时间线合成
        elif synthesis_type == "timeline_synthesis":
            prompt = get_timeline_synthesis_prompt()
            
            # 格式化结果
            if isinstance(results, list):
                formatted_results = self._format_list_results(results)
            else:  # dict
                formatted_results = self._format_dict_results(results)
            
            return prompt, formatted_results
        
        # 解决方案合成
        elif synthesis_type == "solution_synthesis":
            prompt = get_solution_synthesis_prompt()
            
            # 格式化结果
            if isinstance(results, list):
                formatted_results = self._format_list_results(results)
            else:  # dict
                formatted_results = self._format_dict_results(results)
            
            return prompt, formatted_results
        
        # 默认情况（不应该到达这里，因为_validate_input已经检查了合成类型）
        raise AgentError(f"未知的合成类型: {synthesis_type}")
    
    def _format_list_results(self, results: List[Any]) -> str:
        """
        格式化列表结果。
        
        Args:
            results: 结果列表
            
        Returns:
            格式化的结果字符串
        """
        formatted_results = ""
        for i, result in enumerate(results):
            formatted_results += f"结果 {i+1}:\n"
            
            if isinstance(result, dict):
                try:
                    # 尝试格式化为缩进的JSON
                    formatted_results += json.dumps(result, ensure_ascii=False, indent=2)
                except:
                    # 如果JSON序列化失败，则直接转换为字符串
                    formatted_results += str(result)
            else:
                formatted_results += str(result)
            
            formatted_results += "\n\n"
        
        return formatted_results
    
    def _format_dict_results(self, results: Dict[str, Any]) -> str:
        """
        格式化字典结果。
        
        Args:
            results: 结果字典
            
        Returns:
            格式化的结果字符串
        """
        formatted_results = ""
        for key, value in results.items():
            formatted_results += f"{key}:\n"
            
            if isinstance(value, dict):
                try:
                    # 尝试格式化为缩进的JSON
                    formatted_results += json.dumps(value, ensure_ascii=False, indent=2)
                except:
                    # 如果JSON序列化失败，则直接转换为字符串
                    formatted_results += str(value)
            else:
                formatted_results += str(value)
            
            formatted_results += "\n\n"
        
        return formatted_results
    
    def _process_response(self, response: str, synthesis_type: str) -> Dict[str, Any]:
        """
        处理LLM响应。
        
        Args:
            response: LLM响应文本
            synthesis_type: 合成类型
            
        Returns:
            处理后的响应
            
        Raises:
            AgentError: 如果无法处理响应
        """
        # 报告合成不需要解析为JSON
        if synthesis_type == "report_synthesis":
            return {"report": response}
        
        # 其他合成类型需要解析为JSON
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
                    return {"synthesis_text": response}
            except Exception as e:
                error_msg = f"处理响应失败: {str(e)}\n原始响应: {response}"
                logger.error(error_msg)
                # 不抛出异常，而是将原始响应作为文本返回
                return {"synthesis_text": response}
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        获取智能体可用工具列表。
        
        Returns:
            工具列表
        """
        # 合成智能体当前不使用外部工具
        return []
    
    async def synthesize_report(
        self, 
        results: Union[List[Any], Dict[str, Any]], 
        report_type: str, 
        sections: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        合成报告。
        
        Args:
            results: 任务结果列表或字典
            report_type: 报告类型
            sections: 报告章节列表，如果为None则使用默认章节
            
        Returns:
            报告合成结果
        """
        input_data = {
            "results": results,
            "synthesis_type": "report_synthesis",
            "report_type": report_type,
            "sections": sections
        }
        
        return await self.run(input_data)
    
    async def synthesize_findings(
        self, 
        results: Union[List[Any], Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        合成研究发现。
        
        Args:
            results: 任务结果列表或字典
            
        Returns:
            发现合成结果
        """
        input_data = {
            "results": results,
            "synthesis_type": "findings_synthesis"
        }
        
        return await self.run(input_data)
    
    async def synthesize_comparison(
        self, 
        results: Union[List[Any], Dict[str, Any]], 
        comparison_dimensions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        合成比较分析。
        
        Args:
            results: 任务结果列表或字典
            comparison_dimensions: 比较维度列表，如果为None则使用默认维度
            
        Returns:
            比较合成结果
        """
        input_data = {
            "results": results,
            "synthesis_type": "comparative_synthesis",
            "comparison_dimensions": comparison_dimensions
        }
        
        return await self.run(input_data)
    
    async def synthesize_timeline(
        self, 
        events: Union[List[Any], Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        合成时间线。
        
        Args:
            events: 事件列表或字典
            
        Returns:
            时间线合成结果
        """
        input_data = {
            "results": events,
            "synthesis_type": "timeline_synthesis"
        }
        
        return await self.run(input_data)
    
    async def synthesize_solution(
        self, 
        analyses: Union[List[Any], Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        合成解决方案。
        
        Args:
            analyses: 分析结果列表或字典
            
        Returns:
            解决方案合成结果
        """
        input_data = {
            "results": analyses,
            "synthesis_type": "solution_synthesis"
        }
        
        return await self.run(input_data) 