# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
任务分析智能体模块。

负责分析任务要求和复杂度，确定任务类型和处理策略。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain.schema import HumanMessage, SystemMessage
from langchain.schema.runnable import Runnable

from src.taskflow.agents.base import LLMAgent
from src.taskflow.exceptions import AgentError
from src.taskflow.utils.logger import log_execution_time
from src.taskflow.utils.validation import TaskTypeEnum

# 获取日志记录器
logger = logging.getLogger(__name__)


class TaskAnalyzerAgent(LLMAgent[Dict[str, Any], Dict[str, Any]]):
    """
    任务分析智能体。
    
    分析任务要求和复杂度，确定任务类型和适合的处理策略。
    """
    
    def __init__(
        self,
        llm: Runnable,
        name: str = "task_analyzer",
        description: str = "分析任务要求和复杂度，确定任务类型和适合的处理策略",
        metadata: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> None:
        """
        初始化任务分析智能体。
        
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
                "src/prompts/task_analyzer.md",
                "src/prompts/task_analyzer.zh-CN.md"
            ]
            
            for path in prompt_paths:
                prompt = load_prompt_from_file(path)
                if prompt:
                    logger.info(f"已从{path}加载提示词")
                    return prompt
        except Exception as e:
            logger.warning(f"无法从文件加载提示词: {str(e)}")
        
        # 如果无法从文件加载，使用内置提示词
        logger.warning("使用内置的默认任务分析提示词")
        return """
        你是一个专业的任务分析智能体，负责分析任务要求和复杂度。
        
        你的主要任务是：
        1. 确定任务类型（研究、处理、分析、合成等）
        2. 评估任务复杂度
        3. 确定完成任务所需的步骤
        4. 推荐适合的处理智能体和策略
        5. 识别任务的依赖关系和先决条件
        
        任务类型定义：
        - RESEARCH: 需要收集和研究信息的任务
        - PROCESSING: 需要处理和转换数据的任务
        - ANALYSIS: 需要深入分析和评估的任务
        - SYNTHESIS: 需要汇总多个信息源的任务
        - GENERIC: 不属于以上类别的通用任务
        
        请基于提供的任务描述和上下文，输出JSON格式的分析结果，包含以下字段：
        - task_type: 任务类型（必须是上述定义中的一种）
        - complexity: 任务复杂度评分（1-5，其中5最复杂）
        - estimated_time: 预计完成时间（小时）
        - required_steps: 完成任务所需的步骤列表，每个步骤包含名称和描述
        - recommended_agents: 推荐的处理智能体列表
        - dependencies: 任务的依赖关系和先决条件
        - insights: 对任务的额外见解或建议
        
        所有输出都必须是有效的JSON格式。确保你的回答只包含JSON对象，没有其他文本。
        """
    
    @log_execution_time(logger)
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行任务分析智能体。
        
        Args:
            input_data: 输入数据，必须包含"task"字段
            
        Returns:
            任务分析结果
            
        Raises:
            AgentError: 如果无法分析任务
        """
        # 验证输入
        if "task" not in input_data:
            error_msg = "输入数据必须包含'task'字段"
            logger.error(error_msg)
            raise AgentError(error_msg)
        
        task = input_data["task"]
        context = input_data.get("context", {})
        
        logger.info(f"开始分析任务: {task.get('title', 'Unknown')}")
        
        # 准备任务描述
        task_description = self._prepare_task_description(task)
        
        # 构建消息
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"""请分析以下任务：

任务描述：
{task_description}

上下文信息：
{json.dumps(context, ensure_ascii=False, indent=2) if context else "无上下文信息"}
""")
        ]
        
        # 调用LLM
        try:
            response = await self._call_llm(messages)
            logger.debug(f"LLM原始响应: {response}")
            
            # 解析JSON响应
            analysis_result = self._parse_response(response)
            
            # 验证任务类型
            self._validate_task_type(analysis_result)
            
            return analysis_result
        except Exception as e:
            error_msg = f"分析任务时出错: {str(e)}"
            logger.exception(error_msg)
            raise AgentError(error_msg) from e
    
    def _prepare_task_description(self, task: Dict[str, Any]) -> str:
        """
        准备任务描述文本。
        
        Args:
            task: 任务数据
            
        Returns:
            格式化的任务描述
        """
        title = task.get("title", "无标题")
        description = task.get("description", "无描述")
        task_type = task.get("task_type", "未指定")
        
        return f"""标题: {title}
描述: {description}
类型: {task_type}
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
    
    def _validate_task_type(self, analysis_result: Dict[str, Any]) -> None:
        """
        验证任务类型是否有效。
        
        Args:
            analysis_result: 分析结果
            
        Raises:
            AgentError: 如果任务类型无效
        """
        if "task_type" not in analysis_result:
            raise AgentError("分析结果缺少'task_type'字段")
        
        task_type = analysis_result["task_type"]
        valid_task_types = {t.value for t in TaskTypeEnum}
        
        if task_type not in valid_task_types:
            # 尝试将任务类型映射到有效值
            task_type_lower = task_type.upper()
            for valid_type in valid_task_types:
                if valid_type in task_type_lower:
                    analysis_result["task_type"] = valid_type
                    logger.warning(f"任务类型已从'{task_type}'映射到'{valid_type}'")
                    return
            
            # 如果无法映射，使用GENERIC
            analysis_result["task_type"] = "GENERIC"
            logger.warning(f"无效的任务类型'{task_type}'，已设为'GENERIC'")
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        获取智能体可用工具列表。
        
        任务分析智能体当前不使用外部工具。
        
        Returns:
            空工具列表
        """
        return []
    
    async def generate_steps(self, task: Dict[str, Any], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        基于任务和分析生成详细步骤。
        
        Args:
            task: 任务数据
            analysis: 任务分析结果
            
        Returns:
            详细步骤列表
        """
        messages = [
            SystemMessage(content="""
            基于提供的任务和分析结果，生成详细的任务执行步骤。每个步骤应包含：
            1. 步骤名称
            2. 详细描述
            3. 步骤类型
            4. 预计执行时间（分钟）
            5. 所需的智能体类型
            
            请输出JSON格式的步骤列表，每个步骤包含以下字段：
            - name: 步骤名称
            - description: 详细描述
            - step_type: 步骤类型
            - estimated_minutes: 预计执行时间（分钟）
            - agent_type: 所需的智能体类型
            - input_requirements: 步骤输入要求
            - output_expectations: 步骤预期输出
            
            步骤应该是逻辑顺序的，能够完整覆盖任务的所有方面。
            """),
            HumanMessage(content=f"""请为以下任务生成详细步骤：

任务：
{json.dumps(task, ensure_ascii=False, indent=2)}

分析结果：
{json.dumps(analysis, ensure_ascii=False, indent=2)}
""")
        ]
        
        response = await self._call_llm(messages)
        parsed_response = self._parse_response(response)
        
        # 确保返回的是列表
        if isinstance(parsed_response, dict) and "steps" in parsed_response:
            return parsed_response["steps"]
        elif isinstance(parsed_response, list):
            return parsed_response
        else:
            logger.warning(f"步骤生成返回了意外的格式: {type(parsed_response)}")
            # 尝试转换为列表
            if isinstance(parsed_response, dict):
                return [parsed_response]
            return []
    
    async def analyze_dependencies(self, task: Dict[str, Any], other_tasks: List[Dict[str, Any]]) -> List[str]:
        """
        分析任务之间的依赖关系。
        
        Args:
            task: 当前任务
            other_tasks: 其他相关任务
            
        Returns:
            当前任务依赖的任务ID列表
        """
        if not other_tasks:
            return []
        
        messages = [
            SystemMessage(content="""
            分析当前任务与其他任务之间的依赖关系。识别当前任务依赖哪些其他任务。
            
            请输出一个JSON对象，包含以下字段：
            - dependent_task_ids: 当前任务依赖的任务ID列表
            - explanation: 对每个依赖关系的简要解释
            
            只有当其他任务确实是当前任务的前置条件时，才应该将其列为依赖。
            """),
            HumanMessage(content=f"""请分析以下任务之间的依赖关系：

当前任务：
{json.dumps(task, ensure_ascii=False, indent=2)}

其他任务：
{json.dumps(other_tasks, ensure_ascii=False, indent=2)}
""")
        ]
        
        response = await self._call_llm(messages)
        parsed_response = self._parse_response(response)
        
        if "dependent_task_ids" in parsed_response:
            return parsed_response["dependent_task_ids"]
        return [] 