# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
处理智能体模块。

负责处理和转换数据，支持文本、表格等不同类型数据的处理。
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from langchain.schema import HumanMessage, SystemMessage
from langchain.schema.runnable import Runnable

from src.taskflow.agents.base import LLMAgent
from src.taskflow.exceptions import AgentError
from src.taskflow.prompts.processing import (
    get_processing_system_prompt,
    get_text_processing_prompt,
    get_data_transformation_prompt,
    get_data_cleaning_prompt
)
from src.taskflow.utils.logger import log_execution_time

# 获取日志记录器
logger = logging.getLogger(__name__)


class ProcessingAgent(LLMAgent[Dict[str, Any], Dict[str, Any]]):
    """
    处理智能体。
    
    负责处理和转换数据，支持不同类型的处理操作。
    """
    
    def __init__(
        self,
        llm: Runnable,
        name: str = "processing_agent",
        description: str = "处理和转换数据，支持文本、表格等不同类型数据",
        metadata: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> None:
        """
        初始化处理智能体。
        
        Args:
            llm: LLM可运行实例
            name: 智能体名称
            description: 智能体描述
            metadata: 智能体元数据
            system_prompt: 系统提示词，如果为None则使用默认提示词
        """
        # 如果未提供系统提示词，使用默认提示词
        if system_prompt is None:
            system_prompt = get_processing_system_prompt()
        
        super().__init__(name, llm, description, metadata, system_prompt)
    
    @log_execution_time(logger)
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行处理智能体。
        
        Args:
            input_data: 输入数据，必须包含"data"字段和"operation"字段
            
        Returns:
            处理结果
            
        Raises:
            AgentError: 如果处理失败
        """
        # 验证输入
        self._validate_input(input_data)
        
        data = input_data["data"]
        operation = input_data["operation"]
        data_type = input_data.get("data_type", "text")
        
        logger.info(f"开始处理数据，操作类型: {operation}, 数据类型: {data_type}")
        
        # 根据操作类型获取提示词
        prompt_text = self._get_prompt_for_operation(operation, data_type, input_data)
        
        # 构建消息
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"{prompt_text}\n\n{data}")
        ]
        
        # 调用LLM
        try:
            response = await self._call_llm(messages)
            logger.debug(f"LLM原始响应: {response}")
            
            # 解析JSON响应
            result = self._parse_response(response)
            
            # 添加处理元数据
            result["meta"] = {
                "operation": operation,
                "data_type": data_type,
                "processed_by": self.name,
                "processing_parameters": input_data.get("parameters", {})
            }
            
            return result
        except Exception as e:
            error_msg = f"处理数据时出错: {str(e)}"
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
        if "data" not in input_data:
            raise AgentError("输入数据必须包含'data'字段")
        
        if "operation" not in input_data:
            raise AgentError("输入数据必须包含'operation'字段")
        
        # 检查操作类型是否支持
        operation = input_data["operation"]
        supported_operations = [
            "summarize", "extract", "classify", "standardize",  # 文本处理
            "transform", "clean", "filter", "aggregate",  # 数据处理
            "correct", "format"  # 通用处理
        ]
        
        if operation not in supported_operations:
            raise AgentError(f"不支持的操作类型: {operation}，支持的操作类型: {supported_operations}")
    
    def _get_prompt_for_operation(
        self, 
        operation: str, 
        data_type: str, 
        input_data: Dict[str, Any]
    ) -> str:
        """
        根据操作类型获取提示词。
        
        Args:
            operation: 操作类型
            data_type: 数据类型
            input_data: 输入数据
            
        Returns:
            提示词
        """
        # 文本处理操作
        text_operations = ["summarize", "extract", "classify", "standardize"]
        if operation in text_operations:
            extra_instructions = input_data.get("instructions", "")
            return get_text_processing_prompt(operation, extra_instructions)
        
        # 数据转换操作
        if operation == "transform":
            source_format = input_data.get("source_format", "text")
            target_format = input_data.get("target_format", "json")
            extra_instructions = input_data.get("instructions", "")
            return get_data_transformation_prompt(source_format, target_format, extra_instructions)
        
        # 数据清洗操作
        if operation == "clean":
            cleaning_tasks = input_data.get("cleaning_tasks")
            return get_data_cleaning_prompt(data_type, cleaning_tasks)
        
        # 其他操作使用通用提示词
        return f"""
        请对以下{data_type}数据进行{operation}操作。
        
        处理时请考虑：
        1. 确保数据准确性和完整性
        2. 优化数据结构和格式
        3. 提供结果的明确说明
        
        请输出JSON格式的处理结果，包含处理后的数据和处理摘要。
        """
    
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
        # 处理智能体当前不使用外部工具
        return []
    
    async def process_text(
        self, 
        text: str, 
        operation: str, 
        instructions: str = ""
    ) -> Dict[str, Any]:
        """
        处理文本数据。
        
        Args:
            text: 要处理的文本
            operation: 处理操作（summarize、extract、classify、standardize）
            instructions: 额外处理指示
            
        Returns:
            处理结果
        """
        input_data = {
            "data": text,
            "data_type": "text",
            "operation": operation,
            "instructions": instructions
        }
        
        return await self.run(input_data)
    
    async def transform_data(
        self, 
        data: str, 
        source_format: str, 
        target_format: str, 
        instructions: str = ""
    ) -> Dict[str, Any]:
        """
        转换数据格式。
        
        Args:
            data: 要转换的数据
            source_format: 源数据格式
            target_format: 目标数据格式
            instructions: 额外转换指示
            
        Returns:
            转换结果
        """
        input_data = {
            "data": data,
            "data_type": source_format,
            "operation": "transform",
            "source_format": source_format,
            "target_format": target_format,
            "instructions": instructions
        }
        
        return await self.run(input_data)
    
    async def clean_data(
        self, 
        data: str, 
        data_type: str, 
        cleaning_tasks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        清洗数据。
        
        Args:
            data: 要清洗的数据
            data_type: 数据类型
            cleaning_tasks: 清洗任务列表
            
        Returns:
            清洗结果
        """
        input_data = {
            "data": data,
            "data_type": data_type,
            "operation": "clean",
            "cleaning_tasks": cleaning_tasks
        }
        
        return await self.run(input_data) 