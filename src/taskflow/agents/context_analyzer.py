# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
上下文分析智能体模块。

负责分析用户查询和相关上下文，识别研究领域、关键概念和目标类型。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain.schema import HumanMessage, SystemMessage
from langchain.schema.runnable import Runnable

from src.taskflow.agents.base import LLMAgent
from src.taskflow.exceptions import AgentError
from src.taskflow.utils.logger import log_execution_time

# 获取日志记录器
logger = logging.getLogger(__name__)


class ContextAnalyzerAgent(LLMAgent[Dict[str, Any], Dict[str, Any]]):
    """
    上下文分析智能体。
    
    分析用户查询和相关上下文，识别研究领域、关键概念和目标类型。
    """
    
    def __init__(
        self,
        llm: Runnable,
        name: str = "context_analyzer",
        description: str = "分析用户查询和相关上下文，识别研究领域、关键概念和目标类型",
        metadata: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> None:
        """
        初始化上下文分析智能体。
        
        Args:
            llm: LLM可运行实例
            name: 智能体名称
            description: 智能体描述
            metadata: 智能体元数据
            system_prompt: 系统提示词，如果为None则使用默认提示词
        """
        # 如果未提供系统提示词，使用默认提示词
        if system_prompt is None:
            system_prompt = self._get_default_system_prompt()
        
        super().__init__(name, llm, description, metadata, system_prompt)
    
    def _get_default_system_prompt(self) -> str:
        """
        获取默认系统提示词。
        
        注意：此方法仅作为备用，通常应通过get_agent_by_name函数获取智能体实例，
        该函数会自动从/src/prompts/目录加载提示词。
        
        Returns:
            默认系统提示词
        """
        # 尝试从/src/prompts/目录加载
        try:
            from src.taskflow.prompts import load_prompt_from_file
            
            prompt_paths = [
                "src/prompts/context_analyzer.zh-CN.md",
                "src/prompts/context_analyzer.md"
            ]
            
            for path in prompt_paths:
                prompt = load_prompt_from_file(path)
                if prompt:
                    logger.info(f"已从{path}加载提示词")
                    return prompt
        except Exception as e:
            logger.warning(f"无法从文件加载提示词: {str(e)}")
        
        # 如果无法从文件加载，使用内置提示词
        logger.warning("使用内置的默认上下文分析提示词")
        return """
        你是一个专业的上下文分析智能体，负责分析用户查询和相关上下文信息。
        
        你的主要任务是：
        1. 识别查询所涉及的研究领域（例如：法律法规、技术标准、市场分析等）
        2. 提取关键概念和术语
        3. 确定目标类型（例如：信息收集、比较分析、决策支持等）
        4. 识别相关的地理区域或管辖范围
        5. 分析时间约束（如有）
        
        请基于用户查询提供结构化的上下文分析结果，输出为JSON格式，包含以下字段：
        - domain: 主要研究领域
        - secondary_domains: 次要研究领域列表
        - key_concepts: 关键概念列表，每个概念包含名称和简短描述
        - goal_type: 目标类型
        - region: 相关地理区域或管辖范围
        - time_constraints: 时间约束（如有）
        - language: 应使用的语言（默认为中文）
        - complexity: 分析的复杂度评估（1-5，其中5最复杂）
        - information_needs: 完成目标可能需要的信息列表

        所有输出都必须是有效的JSON格式。确保你的回答只包含JSON对象，没有其他文本。
        """
    
    @log_execution_time(logger)
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行上下文分析智能体。
        
        Args:
            input_data: 输入数据，必须包含"query"字段
            
        Returns:
            上下文分析结果
            
        Raises:
            AgentError: 如果无法分析上下文
        """
        # 验证输入
        if "query" not in input_data:
            error_msg = "输入数据必须包含'query'字段"
            logger.error(error_msg)
            raise AgentError(error_msg)
        
        query = input_data["query"]
        logger.info(f"开始分析查询: {query}")
        
        # 构建消息
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"请分析以下查询：\n\n{query}")
        ]
        
        # 调用LLM
        try:
            response = await self._call_llm(messages)
            logger.debug(f"LLM原始响应: {response}")
            
            # 解析JSON响应
            return self._parse_response(response)
        except Exception as e:
            error_msg = f"分析上下文时出错: {str(e)}"
            logger.exception(error_msg)
            raise AgentError(error_msg) from e
    
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
        
        上下文分析智能体当前不使用外部工具。
        
        Returns:
            空工具列表
        """
        return []

    async def analyze_query_complexity(self, query: str) -> Dict[str, Any]:
        """
        分析查询的复杂度。
        
        Args:
            query: 用户查询
            
        Returns:
            复杂度分析结果
        """
        messages = [
            SystemMessage(content="""
            评估用户查询的复杂度，考虑以下因素：
            1. 涉及的领域数量
            2. 需要的专业知识深度
            3. 数据收集的难度
            4. 分析的复杂性
            
            请输出一个JSON对象，包含以下字段：
            - complexity_score: 复杂度评分（1-5，其中5表示最复杂）
            - factors: 影响复杂度的因素列表
            - estimated_completion_time: 估计完成时间（以小时为单位）
            """),
            HumanMessage(content=f"请评估以下查询的复杂度：\n\n{query}")
        ]
        
        response = await self._call_llm(messages)
        return self._parse_response(response)
    
    async def identify_required_resources(self, context_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于上下文分析识别所需资源。
        
        Args:
            context_analysis: 上下文分析结果
            
        Returns:
            所需资源列表
        """
        messages = [
            SystemMessage(content="""
            基于提供的上下文分析，识别完成任务所需的资源，包括：
            1. 数据源类型
            2. 专业知识领域
            3. 可能需要的工具
            4. 参考资料类型
            
            请输出一个JSON对象，包含以下字段：
            - data_sources: 推荐的数据源列表
            - expertise: 所需专业知识列表
            - tools: 推荐的工具列表
            - references: 推荐的参考资料类型
            """),
            HumanMessage(content=f"请基于以下上下文分析识别所需资源：\n\n{json.dumps(context_analysis, ensure_ascii=False, indent=2)}")
        ]
        
        response = await self._call_llm(messages)
        return self._parse_response(response) 