# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow基础智能体模块。

提供智能体的抽象基类和通用功能。
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar, Generic, Union

from langchain.schema import BaseMessage
from langchain.schema.runnable import Runnable

from src.taskflow.exceptions import AgentError

# 获取日志记录器
logger = logging.getLogger(__name__)

# 定义输入和输出类型变量
I = TypeVar('I')  # 输入类型
O = TypeVar('O')  # 输出类型


class BaseAgent(Generic[I, O], ABC):
    """
    智能体基类。
    
    所有特定功能的智能体都应该继承此类。
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        初始化智能体。
        
        Args:
            name: 智能体名称
            description: 智能体描述
            metadata: 智能体元数据
        """
        self.name = name
        self.description = description
        self.metadata = metadata or {}
        self.created_at = datetime.now()
        
        # 初始化日志记录器
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    async def run(self, input_data: I) -> O:
        """
        运行智能体。
        
        Args:
            input_data: 输入数据
            
        Returns:
            输出数据
            
        Raises:
            AgentError: 如果执行失败
        """
        pass
    
    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        获取智能体可用工具列表。
        
        Returns:
            工具定义列表
        """
        pass
    
    def serialize(self) -> Dict[str, Any]:
        """
        序列化智能体配置。
        
        Returns:
            序列化后的配置
        """
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "description": self.description,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


class LLMAgent(BaseAgent[I, O], ABC):
    """
    基于LLM的智能体基类。
    
    提供与LLM交互的通用功能。
    """
    
    def __init__(
        self,
        name: str,
        llm: Runnable,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> None:
        """
        初始化LLM智能体。
        
        Args:
            name: 智能体名称
            llm: LLM可运行实例
            description: 智能体描述
            metadata: 智能体元数据
            system_prompt: 系统提示词
        """
        super().__init__(name, description, metadata)
        self.llm = llm
        self.system_prompt = system_prompt
    
    async def _call_llm(
        self,
        prompt: Union[str, List[BaseMessage]],
        **kwargs
    ) -> Any:
        """
        调用LLM。
        
        Args:
            prompt: 提示词或消息列表
            **kwargs: 其他关键字参数
            
        Returns:
            LLM响应
            
        Raises:
            AgentError: 如果LLM调用失败
        """
        try:
            return await self.llm.ainvoke(prompt, **kwargs)
        except Exception as e:
            error_msg = f"LLM调用失败: {str(e)}"
            self.logger.error(error_msg)
            raise AgentError(error_msg) from e
    
    def serialize(self) -> Dict[str, Any]:
        """
        序列化LLM智能体配置。
        
        Returns:
            序列化后的配置
        """
        base = super().serialize()
        base.update({
            "llm_type": type(self.llm).__name__,
            "has_system_prompt": self.system_prompt is not None,
        })
        return base 