# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow步骤规划智能体模块。

实现将任务规划为详细执行步骤的智能体。
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from langchain.schema import BaseMessage, HumanMessage, SystemMessage
from langchain.schema.runnable import Runnable
from pydantic import BaseModel, Field

from src.taskflow.agents.base import LLMAgent
from src.taskflow.exceptions import AgentError

# 获取日志记录器
logger = logging.getLogger(__name__)


# 输入模型
class StepPlannerInput(BaseModel):
    """步骤规划器的输入模型"""
    
    task_id: str = Field(..., description="任务ID")
    task_title: str = Field(..., description="任务标题")
    task_description: str = Field(..., description="任务详细描述")
    task_type: str = Field(..., description="任务类型")
    objective_id: str = Field(..., description="所属研究目标ID")
    objective_title: str = Field(..., description="所属研究目标标题")
    objective_query: Optional[str] = Field(None, description="原始研究查询")
    estimated_steps: Optional[List[str]] = Field(None, description="预估步骤")
    context: Optional[Dict[str, Any]] = Field(None, description="附加上下文信息")


# 输出步骤模型
class PlannedStep(BaseModel):
    """规划的步骤模型"""
    
    name: str = Field(..., description="步骤名称")
    description: str = Field(..., description="步骤详细描述")
    step_type: str = Field(..., description="步骤类型")
    agent_type: Optional[str] = Field(None, description="执行该步骤的智能体类型")
    priority: int = Field(0, description="优先级（0-10）")
    input_data: Optional[Dict[str, Any]] = Field(None, description="步骤输入数据")
    estimated_time: Optional[int] = Field(None, description="预估完成时间（分钟）")


# 输出模型
class StepPlannerOutput(BaseModel):
    """步骤规划器的输出模型"""
    
    task_id: str = Field(..., description="任务ID")
    task_title: str = Field(..., description="任务标题")
    reasoning: str = Field(..., description="规划推理过程")
    steps: List[PlannedStep] = Field(..., description="规划的步骤列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="规划器元数据")


class StepPlannerAgent(LLMAgent[StepPlannerInput, StepPlannerOutput]):
    """
    步骤规划智能体。
    
    负责将任务规划为具体可执行的步骤序列。
    """
    
    def __init__(
        self,
        llm: Runnable,
        name: str = "step_planner",
        description: str = "将任务规划为具体执行步骤",
        metadata: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> None:
        """
        初始化步骤规划智能体。
        
        Args:
            llm: LLM可运行实例
            name: 智能体名称
            description: 智能体描述
            metadata: 智能体元数据
            system_prompt: 自定义系统提示词
        """
        # 使用默认系统提示词
        default_system_prompt = """你是一个专业的步骤规划助手，擅长将任务分解为详细的、可执行的步骤序列。

你的责任是：
1. 分析任务的各个方面和需求
2. 将任务分解为明确的执行步骤（通常3-7个）
3. 确保步骤覆盖任务的所有关键方面
4. 确定步骤的逻辑执行顺序
5. 为每个步骤分配合适的优先级
6. 确定执行每个步骤的最佳智能体类型

支持的智能体类型包括：
- researcher: 研究型智能体，擅长信息搜索和数据收集
- analyzer: 分析型智能体，擅长数据分析和模式识别
- developer: 开发型智能体，擅长编写代码和构建系统
- tester: 测试型智能体，擅长验证结果和发现问题
- evaluator: 评估型智能体，擅长评估质量和提供反馈
- summarizer: 总结型智能体，擅长整合信息和生成摘要

对于每个步骤，你需要确定：
- 清晰的名称和描述
- 适当的步骤类型（研究、分析、开发、测试、评估、总结等）
- 执行优先级（0-10，10为最高）
- 执行该步骤的智能体类型
- 预估完成时间（分钟）
- 步骤输入数据（如有必要）

请确保你的计划是全面的、逻辑的，并且包含足够的信息以便智能体执行。
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
        # 步骤规划器不需要额外工具
        return []
    
    def _build_messages(self, input_data: StepPlannerInput) -> List[BaseMessage]:
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
            f"# 任务信息\n标题: {input_data.task_title}",
            f"描述: {input_data.task_description}",
            f"类型: {input_data.task_type}",
            f"\n# 所属研究目标\n标题: {input_data.objective_title}",
        ]
        
        if input_data.objective_query:
            content.append(f"查询: {input_data.objective_query}")
        
        if input_data.estimated_steps:
            steps_str = "\n".join([f"- {step}" for step in input_data.estimated_steps])
            content.append(f"\n# 预估步骤\n{steps_str}")
        
        if input_data.context:
            context_str = json.dumps(input_data.context, ensure_ascii=False, indent=2)
            content.append(f"\n# 附加上下文\n```json\n{context_str}\n```")
        
        content.append("\n请将这个任务规划为详细的执行步骤。对于每个步骤，提供名称、描述、步骤类型、智能体类型、优先级和预估完成时间。")
        content.append("\n以JSON格式返回结果，结构如下：")
        content.append("""
```json
{
  "reasoning": "你进行规划的推理过程...",
  "steps": [
    {
      "name": "步骤1名称",
      "description": "详细描述",
      "step_type": "研究|分析|开发|测试|评估|总结等",
      "agent_type": "researcher|analyzer|developer|tester|evaluator|summarizer",
      "priority": 5,
      "estimated_time": 30,
      "input_data": {"key": "value"}
    },
    ...
  ]
}
```
""")
        
        human_message = HumanMessage(content="\n".join(content))
        messages.append(human_message)
        
        return messages
    
    def _parse_llm_response(self, response: Any) -> StepPlannerOutput:
        """
        解析LLM响应。
        
        Args:
            response: LLM响应
            
        Returns:
            规划输出
            
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
            if "steps" not in data or not isinstance(data["steps"], list):
                raise ValueError("Response missing 'steps' array")
            
            if "reasoning" not in data or not isinstance(data["reasoning"], str):
                data["reasoning"] = "未提供推理过程"
            
            # 创建输出对象
            return StepPlannerOutput(
                task_id=self.input_data.task_id,
                task_title=self.input_data.task_title,
                reasoning=data["reasoning"],
                steps=[PlannedStep(**step) for step in data["steps"]],
                metadata={"generated_by": self.name}
            )
        
        except Exception as e:
            error_msg = f"解析LLM响应失败: {str(e)}, 原始响应: {response}"
            self.logger.error(error_msg)
            raise AgentError(error_msg) from e
    
    async def run(self, input_data: StepPlannerInput) -> StepPlannerOutput:
        """
        运行智能体。
        
        Args:
            input_data: 输入数据
            
        Returns:
            规划后的步骤
            
        Raises:
            AgentError: 如果执行失败
        """
        try:
            self.logger.info(f"规划任务步骤: {input_data.task_title}, ID: {input_data.task_id}")
            
            # 保存输入数据(用于_parse_llm_response)
            self.input_data = input_data
            
            # 构建消息
            messages = self._build_messages(input_data)
            
            # 调用LLM
            response = await self._call_llm(messages)
            
            # 解析响应
            result = self._parse_llm_response(response)
            
            self.logger.info(f"任务步骤规划完成: {input_data.task_id}, 生成{len(result.steps)}个步骤")
            return result
            
        except Exception as e:
            error_msg = f"任务步骤规划失败: {str(e)}"
            self.logger.error(error_msg)
            raise AgentError(error_msg) from e 