# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow LLM工厂模块。

提供创建和管理LLM实例的工厂类。
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List, Union

from langchain.schema import BaseMessage
from langchain.schema.runnable import Runnable
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.taskflow.config.settings import settings
from src.taskflow.config.agents import LLMType, get_agent_llm_type, get_task_llm_type

# 获取日志记录器
logger = logging.getLogger(__name__)


class LLMFactory:
    """
    LLM工厂类。
    
    提供创建和管理不同配置LLM实例的功能。
    """
    
    def __init__(self) -> None:
        """初始化LLM工厂"""
        self._llm_cache: Dict[str, Runnable] = {}
        self._type_cache: Dict[str, Runnable] = {}  # 按类型缓存
        self._default_model = settings.llm.model_name
        self._default_temperature = settings.llm.temperature
    
    def get_llm_by_type(self, llm_type: LLMType) -> Runnable:
        """
        根据LLM类型获取LLM实例。
        
        Args:
            llm_type: LLM类型
            
        Returns:
            可运行的LLM实例
        """
        # 如果已缓存，直接返回
        if llm_type in self._type_cache:
            return self._type_cache[llm_type]
        
        # 从配置中获取对应类型的LLM配置
        llm_config = settings.llm.get_llm_config_by_type(llm_type)
        
        # 创建LLM实例
        llm = self.create_llm(
            model_name=llm_config.get("model"),
            temperature=llm_config.get("temperature"),
            max_tokens=llm_config.get("max_tokens"),
            api_key=llm_config.get("api_key"),
            base_url=llm_config.get("base_url"),
        )
        
        # 缓存并返回LLM实例
        self._type_cache[llm_type] = llm
        return llm
    
    def get_llm_for_agent(self, agent_type: str) -> Runnable:
        """
        根据智能体类型获取LLM实例。
        
        Args:
            agent_type: 智能体类型
            
        Returns:
            可运行的LLM实例
        """
        # 获取智能体类型对应的LLM类型
        llm_type = get_agent_llm_type(agent_type)
        
        # 根据LLM类型获取LLM实例
        return self.get_llm_by_type(llm_type)
    
    def get_llm_for_task(self, task_type: str) -> Runnable:
        """
        根据任务类型获取LLM实例。
        
        Args:
            task_type: 任务类型
            
        Returns:
            可运行的LLM实例
        """
        # 获取任务类型对应的LLM类型
        llm_type = get_task_llm_type(task_type)
        
        # 根据LLM类型获取LLM实例
        return self.get_llm_by_type(llm_type)
    
    def create_llm(
        self,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ) -> Runnable:
        """
        创建LLM实例。
        
        Args:
            model_name: 模型名称，如果未提供则使用配置中的默认值
            temperature: 温度参数，如果未提供则使用配置中的默认值
            max_tokens: 最大令牌数，如果未提供则使用配置中的默认值
            api_key: API密钥，如果未提供则使用配置中的默认值
            base_url: API基础URL，如果未提供则使用配置中的默认值
            **kwargs: 传递给LLM的其他参数
            
        Returns:
            可运行的LLM实例
        """
        # 使用默认值，如果未提供参数
        model = model_name or self._default_model
        temp = temperature if temperature is not None else self._default_temperature
        tokens = max_tokens or settings.llm.max_tokens
        key = api_key or settings.llm.api_key
        url = base_url or settings.llm.api_base
        
        # 创建缓存键
        cache_key = f"{model}_{temp}_{tokens}"
        if key:
            cache_key += f"_{key[:8]}..."  # 只使用密钥的前8个字符
        if url:
            cache_key += f"_{url}"
        for k, v in sorted(kwargs.items()):
            cache_key += f"_{k}_{v}"
        
        # 如果已经有缓存的实例，直接返回
        if cache_key in self._llm_cache:
            return self._llm_cache[cache_key]
        
        # 创建LLM实例
        llm_type = settings.llm.model_type.lower()
        
        if llm_type == "openai":
            llm = ChatOpenAI(
                model=model,
                temperature=temp,
                max_tokens=tokens,
                api_key=key,
                base_url=url or None,
                **kwargs
            )
        else:
            # 如果需要支持其他LLM（如本地模型），可以在这里添加
            logger.warning(f"不支持的LLM类型：{llm_type}，使用OpenAI作为后备")
            llm = ChatOpenAI(
                model=model,
                temperature=temp,
                max_tokens=tokens,
                api_key=key,
                base_url=url or None,
                **kwargs
            )
        
        # 缓存并返回LLM实例
        self._llm_cache[cache_key] = llm
        logger.info(f"创建新的LLM实例：{model}, temperature={temp}")
        
        return llm
    
    def create_chain(
        self,
        prompt_template: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        output_parser: Optional[Callable] = None,
        **kwargs
    ) -> Runnable:
        """
        创建LLM链。
        
        Args:
            prompt_template: 提示模板
            model_name: 模型名称，如果未提供则使用默认值
            temperature: 温度参数，如果未提供则使用默认值
            output_parser: 输出解析器，如果未提供则使用StrOutputParser
            **kwargs: 传递给LLM的其他参数
            
        Returns:
            可运行的LLM链
        """
        # 创建提示模板
        prompt = ChatPromptTemplate.from_template(prompt_template)
        
        # 创建LLM实例
        llm = self.create_llm(
            model_name=model_name,
            temperature=temperature,
            **kwargs
        )
        
        # 创建输出解析器
        parser = output_parser or StrOutputParser()
        
        # 创建链
        chain = prompt | llm | parser
        
        return chain
    
    def create_multi_prompt_chain(
        self,
        prompt_templates: List[str],
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        output_parser: Optional[Callable] = None,
        **kwargs
    ) -> Runnable:
        """
        创建多提示LLM链。
        
        该链将按顺序执行多个提示。
        
        Args:
            prompt_templates: 提示模板列表
            model_name: 模型名称，如果未提供则使用默认值
            temperature: 温度参数，如果未提供则使用默认值
            output_parser: 输出解析器，如果未提供则使用StrOutputParser
            **kwargs: 传递给LLM的其他参数
            
        Returns:
            可运行的LLM链
        """
        chains = []
        for template in prompt_templates:
            chain = self.create_chain(
                prompt_template=template,
                model_name=model_name,
                temperature=temperature,
                output_parser=None,  # 只对最后一个链使用解析器
                **kwargs
            )
            chains.append(chain)
        
        # 创建输出解析器
        parser = output_parser or StrOutputParser()
        
        # 将链连接起来
        combined_chain = chains[0]
        for chain in chains[1:]:
            combined_chain = combined_chain | chain
        
        # 添加输出解析器
        combined_chain = combined_chain | parser
        
        return combined_chain
    
    def clear_cache(self) -> None:
        """清除LLM缓存"""
        self._llm_cache.clear()
        self._type_cache.clear()
        logger.info("已清除LLM缓存")


# 创建全局工厂实例
llm_factory = LLMFactory()


def get_llm_by_type(llm_type: LLMType) -> Runnable:
    """
    根据LLM类型获取LLM实例。
    
    Args:
        llm_type: LLM类型
        
    Returns:
        可运行的LLM实例
    """
    return llm_factory.get_llm_by_type(llm_type)


def get_llm_for_agent(agent_type: str) -> Runnable:
    """
    根据智能体类型获取LLM实例。
    
    Args:
        agent_type: 智能体类型
        
    Returns:
        可运行的LLM实例
    """
    return llm_factory.get_llm_for_agent(agent_type)


def get_llm_for_task(task_type: str) -> Runnable:
    """
    根据任务类型获取LLM实例。
    
    Args:
        task_type: 任务类型
        
    Returns:
        可运行的LLM实例
    """
    return llm_factory.get_llm_for_task(task_type) 