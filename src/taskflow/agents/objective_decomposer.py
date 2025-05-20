# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow目标分解器智能体模块。

实现将复杂研究目标分解为可执行任务的智能体。
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from langchain.schema import BaseMessage, HumanMessage, SystemMessage
from langchain.schema.runnable import Runnable
from pydantic import BaseModel, Field

from src.taskflow.agents.base import LLMAgent
from src.taskflow.exceptions import AgentError

# 获取日志记录器
logger = logging.getLogger(__name__)


# 输入模型
class ObjectiveDecomposerInput(BaseModel):
    """目标分解器的输入模型"""
    
    objective_id: str = Field(..., description="研究目标ID")
    objective_title: str = Field(..., description="研究目标标题")
    objective_description: Optional[str] = Field(None, description="研究目标详细描述")
    objective_query: str = Field(..., description="原始研究查询")
    context: Optional[Dict[str, Any]] = Field(None, description="附加上下文信息")


# 输出任务模型
class DecomposedTask(BaseModel):
    """分解后的任务模型"""
    
    title: str = Field(..., description="任务标题")
    description: str = Field(..., description="任务详细描述")
    task_type: str = Field(..., description="任务类型")
    priority: int = Field(0, description="优先级（0-10）")
    estimated_steps: List[str] = Field(..., description="预估步骤")
    depends_on: Optional[List[str]] = Field(None, description="依赖的任务标题列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="任务元数据")


# 输出模型
class ObjectiveDecomposerOutput(BaseModel):
    """目标分解器的输出模型"""
    
    objective_id: str = Field(..., description="研究目标ID")
    objective_title: str = Field(..., description="研究目标标题")
    reasoning: str = Field(..., description="分解推理过程")
    tasks: List[DecomposedTask] = Field(..., description="分解的任务列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="分解器元数据")


class ObjectiveDecomposerAgent(LLMAgent[ObjectiveDecomposerInput, ObjectiveDecomposerOutput]):
    """
    目标分解器智能体。
    
    负责将复杂研究目标分解为具体可执行的任务序列。
    """
    
    def __init__(
        self,
        llm: Runnable,
        name: str = "objective_decomposer",
        description: str = "将复杂研究目标分解为可执行任务",
        metadata: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> None:
        """
        初始化目标分解器智能体。
        
        Args:
            llm: LLM可运行实例
            name: 智能体名称
            description: 智能体描述
            metadata: 智能体元数据
            system_prompt: 自定义系统提示词
        """
        # 使用默认系统提示词
        default_system_prompt = """你是一个专门的目标分解器助手，擅长将复杂的研究目标分解为明确的、可执行的任务序列。

你的责任是：
1. 分析复杂研究目标的各个方面
2. 将大目标分解为合理数量的任务（通常5-10个）
3. 确保任务覆盖目标的所有关键方面
4. 确定任务之间的依赖关系
5. 为每个任务分配合适的优先级
6. 为每个任务确定大致的执行步骤

对于每个任务，你需要确定：
- 清晰的标题和描述
- 适当的任务类型（研究、分析、开发、测试、评估等）
- 执行优先级（0-10，10为最高）
- 预估的执行步骤
- 与其他任务的依赖关系

请确保你的分解是全面的、逻辑的，并且包含足够的信息以便其他智能体执行。
"""

        super().__init__(
            name=name,
            llm=llm,
            description=description,
            metadata=metadata,
            system_prompt=system_prompt or default_system_prompt
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        获取智能体工具列表。
        
        Returns:
            工具定义列表
        """
        # 目标分解器不需要额外工具
        return []
    
    def _build_messages(self, input_data: ObjectiveDecomposerInput) -> List[BaseMessage]:
        """
        构建提示消息。
        
        Args:
            input_data: 输入数据
            
        Returns:
            消息列表
        """
        # 系统提示
        messages = [SystemMessage(content=self.system_prompt)]
        
        # 构建人类消息
        content = [
            f"# 研究目标\n标题: {input_data.objective_title}",
        ]
        
        if input_data.objective_description:
            content.append(f"描述: {input_data.objective_description}")
        
        content.append(f"查询: {input_data.objective_query}")
        
        if input_data.context:
            context_str = json.dumps(input_data.context, ensure_ascii=False, indent=2)
            content.append(f"\n# 附加上下文\n```json\n{context_str}\n```")
        
        content.append("\n请将这个研究目标分解为合理数量的任务。对于每个任务，提供标题、描述、任务类型、优先级、预估步骤和依赖关系。")
        content.append("\n以JSON格式返回结果，结构如下：")
        content.append("""
```json
{
  "reasoning": "你进行分解的推理过程...",
  "tasks": [
    {
      "title": "任务1标题",
      "description": "详细描述",
      "task_type": "研究|分析|开发|测试|评估等",
      "priority": 5,
      "estimated_steps": ["步骤1", "步骤2", "..."],
      "depends_on": ["依赖的任务标题1", "..."]
    },
    ...
  ]
}
```
""")
        
        human_message = HumanMessage(content="\n".join(content))
        messages.append(human_message)
        
        return messages
    
    def _parse_llm_response(self, response: Any) -> ObjectiveDecomposerOutput:
        """
        解析LLM响应。
        
        Args:
            response: LLM响应
            
        Returns:
            分解输出
            
        Raises:
            AgentError: 如果解析失败
        """
        try:
            # 提取JSON部分
            content = response.content if hasattr(response, "content") else str(response)
            
            # 查找JSON块
            json_content = content
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end > start:
                    json_content = content[start:end].strip()
            
            # 解析JSON
            data = json.loads(json_content)
            
            # 验证关键字段
            if "tasks" not in data or not isinstance(data["tasks"], list):
                raise ValueError("Response missing 'tasks' array")
            
            if "reasoning" not in data or not isinstance(data["reasoning"], str):
                data["reasoning"] = "未提供推理过程"
            
            # 创建输出对象
            return ObjectiveDecomposerOutput(
                objective_id=self.input_data.objective_id,
                objective_title=self.input_data.objective_title,
                reasoning=data["reasoning"],
                tasks=[DecomposedTask(**task) for task in data["tasks"]],
                metadata={"generated_by": self.name}
            )
        
        except Exception as e:
            error_msg = f"解析LLM响应失败: {str(e)}, 原始响应: {response}"
            self.logger.error(error_msg)
            raise AgentError(error_msg) from e
    
    async def run(self, input_data: ObjectiveDecomposerInput) -> ObjectiveDecomposerOutput:
        """
        运行智能体。
        
        Args:
            input_data: 输入数据
            
        Returns:
            分解后的目标任务
            
        Raises:
            AgentError: 如果执行失败
        """
        try:
            self.logger.info(f"分解目标: {input_data.objective_title}, ID: {input_data.objective_id}")
            
            # 保存输入数据(用于_parse_llm_response)
            self.input_data = input_data
            
            # 构建消息
            messages = self._build_messages(input_data)
            
            # 调用LLM
            response = await self._call_llm(messages)
            
            # 解析响应
            result = self._parse_llm_response(response)
            
            self.logger.info(f"目标分解完成: {input_data.objective_id}, 生成{len(result.tasks)}个任务")
            return result
            
        except Exception as e:
            error_msg = f"目标分解失败: {str(e)}"
            self.logger.error(error_msg)
            raise AgentError(error_msg) from e 