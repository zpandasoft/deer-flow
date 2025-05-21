# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow智能体工厂模块。

提供创建和管理智能体实例的工厂类。
"""

import logging
from typing import Dict, Any, Optional, Type, TypeVar, Generic, cast

from src.taskflow.agents.base import BaseAgent
from src.taskflow.agents.context_analyzer import ContextAnalyzerAgent
from src.taskflow.agents.error_handler import ErrorHandlerAgent
from src.taskflow.agents.objective_decomposer import ObjectiveDecomposerAgent
from src.taskflow.agents.processing_agent import ProcessingAgent
from src.taskflow.agents.quality_evaluator import QualityEvaluatorAgent
from src.taskflow.agents.research_agent import ResearchAgent
from src.taskflow.agents.step_planner import StepPlannerAgent
from src.taskflow.agents.synthesis_agent import SynthesisAgent
from src.taskflow.agents.task_analyzer import TaskAnalyzerAgent
from src.taskflow.exceptions import AgentError
from src.taskflow.llm.factory import llm_factory

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
        
        # 注册所有智能体类型
        self._register_all_agents()
    
    def _register_all_agents(self) -> None:
        """注册所有内置智能体类型"""
        # 基础智能体
        self.register_agent_class("context_analyzer", ContextAnalyzerAgent)
        self.register_agent_class("error_handler", ErrorHandlerAgent)
        self.register_agent_class("objective_decomposer", ObjectiveDecomposerAgent)
        self.register_agent_class("processing", ProcessingAgent)
        self.register_agent_class("quality_evaluator", QualityEvaluatorAgent)
        self.register_agent_class("research", ResearchAgent)
        self.register_agent_class("step_planner", StepPlannerAgent)
        self.register_agent_class("synthesis", SynthesisAgent)
        self.register_agent_class("task_analyzer", TaskAnalyzerAgent)
        
        # 别名支持
        self.register_agent_class("processing_agent", ProcessingAgent)
        self.register_agent_class("research_agent", ResearchAgent)
    
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
            # 使用LLM工厂为该智能体类型创建LLM实例
            kwargs["llm"] = llm_factory.get_llm_for_agent(agent_type)
        
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

def get_agent_by_name(agent_type: str, **kwargs) -> BaseAgent:
    """
    获取智能体实例。
    
    此函数会加载/src/prompts/目录下的提示词文件作为智能体的系统提示词。
    
    Args:
        agent_type: 智能体类型名称
        **kwargs: 传递给智能体构造函数的其他参数
        
    Returns:
        智能体实例
    """
    # 尝试加载/src/prompts/目录下对应的提示词
    try:
        from src.taskflow.prompts import load_prompt_from_file
        
        # 确定语言版本（优先使用中文）
        language = kwargs.get("language", "zh-CN")
        
        # 尝试按以下顺序查找提示词文件:
        # 1. [agent_type].[language].md - 有语言后缀的markdown文件
        # 2. [agent_type]-[language].md - 带语言代码的markdown文件
        # 3. [agent_type]_[language].md - 带语言代码的markdown文件
        # 4. [agent_type].md - 默认markdown文件
        # 5. [agent_type].txt - 纯文本文件
        prompt_paths = [
            f"src/prompts/{agent_type}.{language}.md",
            f"src/prompts/{agent_type}-{language}.md", 
            f"src/prompts/{agent_type}_{language}.md",
            f"src/prompts/{agent_type}.md",
            f"src/prompts/{agent_type}.txt"
        ]
        
        # 尝试加载第一个存在的提示词文件
        system_prompt = None
        for path in prompt_paths:
            system_prompt = load_prompt_from_file(path)
            if system_prompt:
                logger.info(f"已加载智能体'{agent_type}'的提示词从文件: {path}")
                break
        
        # 如果加载成功，将提示词传递给智能体
        if system_prompt:
            kwargs["system_prompt"] = system_prompt
    except Exception as e:
        logger.warning(f"无法加载智能体'{agent_type}'的提示词: {str(e)}")
    
    # 使用工厂创建智能体
    return agent_factory.get_agent(agent_type, **kwargs) 