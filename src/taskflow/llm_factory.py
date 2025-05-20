# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow LLM工厂模块。

提供创建和管理LLM实例的工厂类。
"""

import logging
from typing import Dict, Any, Optional, Callable, List

from langchain.schema.runnable import Runnable
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.taskflow.config.settings import settings

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
        self._default_model = settings.llm.model_name
        self._default_temperature = settings.llm.temperature
    
    def create_llm(
        self,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Runnable:
        """
        创建LLM实例。
        
        Args:
            model_name: 模型名称，如果未提供则使用配置中的默认值
            temperature: 温度参数，如果未提供则使用配置中的默认值
            max_tokens: 最大令牌数，如果未提供则使用配置中的默认值
            **kwargs: 传递给LLM的其他参数
            
        Returns:
            可运行的LLM实例
        """
        # 使用默认值，如果未提供参数
        model = model_name or self._default_model
        temp = temperature if temperature is not None else self._default_temperature
        tokens = max_tokens or settings.llm.max_tokens
        
        # 创建缓存键
        cache_key = f"{model}_{temp}_{tokens}"
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
                api_key=settings.llm.api_key,
                base_url=settings.llm.api_base or None,
                **kwargs
            )
        else:
            # 如果需要支持其他LLM（如本地模型），可以在这里添加
            logger.warning(f"不支持的LLM类型：{llm_type}，使用OpenAI作为后备")
            llm = ChatOpenAI(
                model=model,
                temperature=temp,
                max_tokens=tokens,
                api_key=settings.llm.api_key,
                base_url=settings.llm.api_base or None,
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
            prompt_template: 提示词模板
            model_name: 模型名称，如果未提供则使用配置中的默认值
            temperature: 温度参数，如果未提供则使用配置中的默认值
            output_parser: 输出解析器，如果未提供则使用字符串解析器
            **kwargs: 传递给LLM的其他参数
            
        Returns:
            可运行的LLM链
        """
        # 创建LLM实例
        llm = self.create_llm(model_name, temperature, **kwargs)
        
        # 创建提示词模板
        prompt = ChatPromptTemplate.from_template(prompt_template)
        
        # 使用默认解析器，如果未提供
        parser = output_parser or StrOutputParser()
        
        # 创建链
        chain = prompt | llm | parser
        
        return chain


# 创建全局LLM工厂实例
llm_factory = LLMFactory() 