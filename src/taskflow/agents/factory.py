# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow智能体工厂模块。

提供创建和管理智能体实例的工厂类。
"""

import logging
from typing import Dict, Any, Optional, Type, TypeVar, Generic, cast

from src.taskflow.agents.base import BaseAgent
from src.taskflow.agents.objective_decomposer import ObjectiveDecomposerAgent
from src.taskflow.agents.step_planner import StepPlannerAgent
from src.taskflow.exceptions import AgentError
from src.taskflow.llm_factory import llm_factory

# 获取日志记录器
logger = logging.getLogger(__name__)

# 定义类型变量
T = TypeVar('T', bound=BaseAgent)


class AgentFactory:
    """
    智能体工厂类。
    
    提供创建和管理不同类型智能体实例的功能。
    """
    
    def __init__(self) -> None:
        """初始化智能体工厂"""
        self._agent_cache: Dict[str, BaseAgent] = {}
        self._agent_classes: Dict[str, Type[BaseAgent]] = {}
        
        # 注册内置智能体类型
        self.register_agent_class("objective_decomposer", ObjectiveDecomposerAgent)
        self.register_agent_class("step_planner", StepPlannerAgent)
    
    def register_agent_class(self, agent_type: str, agent_class: Type[BaseAgent]) -> None:
        """
        注册智能体类。
        
        Args:
            agent_type: 智能体类型名称
            agent_class: 智能体类
        """
        self._agent_classes[agent_type] = agent_class
        logger.info(f"已注册智能体类型: {agent_type}")
    
    def create_agent(
        self,
        agent_type: str,
        name: Optional[str] = None,
        **kwargs
    ) -> BaseAgent:
        """
        创建智能体实例。
        
        Args:
            agent_type: 智能体类型
            name: 智能体名称，如果未提供则使用类型作为名称
            **kwargs: 传递给智能体构造函数的其他参数
            
        Returns:
            智能体实例
            
        Raises:
            AgentError: 如果智能体类型未注册
        """
        # 使用类型作为名称，如果未提供
        agent_name = name or agent_type
        
        # 创建缓存键
        cache_key = f"{agent_type}_{agent_name}"
        
        # 如果已经有缓存的实例，直接返回
        if cache_key in self._agent_cache:
            return self._agent_cache[cache_key]
        
        # 检查智能体类型是否已注册
        if agent_type not in self._agent_classes:
            error_msg = f"未知的智能体类型: {agent_type}"
            logger.error(error_msg)
            raise AgentError(error_msg)
        
        # 获取智能体类
        agent_class = self._agent_classes[agent_type]
        
        # 对于LLM智能体，如果未提供LLM，则创建一个
        if "llm" not in kwargs and hasattr(agent_class, "_call_llm"):
            # 使用LLM工厂创建LLM实例
            kwargs["llm"] = llm_factory.create_llm()
        
        # 创建智能体实例
        try:
            agent = agent_class(name=agent_name, **kwargs)
            
            # 缓存并返回智能体实例
            self._agent_cache[cache_key] = agent
            logger.info(f"创建新的智能体实例: {agent_type}, name={agent_name}")
            
            return agent
        except Exception as e:
            error_msg = f"创建智能体失败: {str(e)}"
            logger.error(error_msg)
            raise AgentError(error_msg) from e
    
    def get_agent(
        self,
        agent_type: str,
        name: Optional[str] = None,
        **kwargs
    ) -> BaseAgent:
        """
        获取智能体实例，如果不存在则创建。
        
        Args:
            agent_type: 智能体类型
            name: 智能体名称，如果未提供则使用类型作为名称
            **kwargs: 传递给智能体构造函数的其他参数
            
        Returns:
            智能体实例
        """
        return self.create_agent(agent_type, name, **kwargs)
    
    def get_agent_typed(
        self,
        agent_type: str,
        agent_class: Type[T],
        name: Optional[str] = None,
        **kwargs
    ) -> T:
        """
        获取带有类型信息的智能体实例。
        
        Args:
            agent_type: 智能体类型
            agent_class: 期望的智能体类
            name: 智能体名称，如果未提供则使用类型作为名称
            **kwargs: 传递给智能体构造函数的其他参数
            
        Returns:
            智能体实例，带有正确的类型
        """
        agent = self.create_agent(agent_type, name, **kwargs)
        return cast(agent_class, agent)
    
    def clear_cache(self) -> None:
        """清除智能体缓存"""
        self._agent_cache.clear()
        logger.info("已清除智能体缓存")


# 创建全局智能体工厂实例
agent_factory = AgentFactory() 