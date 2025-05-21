#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TaskFlow LLM使用示例。

本示例展示了如何在TaskFlow中使用各种LLM配置和调用方式。
"""

import asyncio
import logging
from typing import List, Dict, Any

from langchain.schema import HumanMessage

# 设置日志级别
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 从taskflow导入LLM相关模块
from src.taskflow.llm_factory import (
    get_llm_by_type,           # 根据LLM类型获取LLM
    get_llm_for_agent,         # 根据智能体类型获取LLM
    get_llm_for_task,          # 根据任务类型获取LLM
    llm_factory                # LLM工厂实例
)


async def example_direct_llm_calls():
    """演示直接调用LLM实例"""
    logger.info("=== 演示1: 直接调用LLM实例 ===")
    
    # 示例1: 使用LLM类型获取LLM
    basic_llm = get_llm_by_type("basic")
    response = await basic_llm.ainvoke([HumanMessage(content="你好，介绍一下TaskFlow")])
    logger.info(f"基础LLM响应: {response.content}")
    
    # 示例2: 使用智能体类型获取LLM
    planner_llm = get_llm_for_agent("planner")
    response = await planner_llm.ainvoke([HumanMessage(content="为研究量子计算制定一个计划")])
    logger.info(f"规划器LLM响应: {response.content[:100]}...")  # 只显示前100个字符
    
    # 示例3: 使用任务类型获取LLM
    coding_llm = get_llm_for_task("code_generation")
    response = await coding_llm.ainvoke([HumanMessage(content="用Python写一个简单的计数器类")])
    logger.info(f"编码LLM响应: {response.content[:100]}...")


async def example_advanced_llm_usage():
    """演示高级LLM用法"""
    logger.info("\n=== 演示2: 高级LLM用法 ===")
    
    # 示例1: 创建自定义参数的LLM
    custom_llm = llm_factory.create_llm(
        model_name="gpt-4-turbo-preview",
        temperature=0.7,  # 增加创造性
        max_tokens=2000
    )
    response = await custom_llm.ainvoke([HumanMessage(content="写一个关于AI的短诗")])
    logger.info(f"自定义LLM响应: {response.content}")
    
    # 示例2: 创建带结构化输出的LLM
    from langchain_core.pydantic_v1 import BaseModel, Field
    
    class ResearchTopic(BaseModel):
        """研究主题模型"""
        title: str = Field(description="研究主题标题")
        key_points: List[str] = Field(description="关键点列表")
        difficulty: int = Field(description="难度等级，1-5")
    
    structured_llm = get_llm_by_type("reasoning").with_structured_output(ResearchTopic)
    response = await structured_llm.ainvoke([HumanMessage(content="提出一个关于量子计算的研究主题")])
    logger.info(f"结构化输出: {response.model_dump_json(indent=2)}")


async def example_chain_usage():
    """演示使用LLM链"""
    logger.info("\n=== 演示3: 使用LLM链 ===")
    
    # 创建简单的LLM链
    prompt_template = """
    你是一位专业的{role}。请{action}关于{topic}的内容。

    要求:
    1. 简洁明了
    2. 针对初学者
    3. 提供实际示例

    主题: {topic}
    """
    
    chain = llm_factory.create_chain(
        prompt_template=prompt_template,
        model_name="gpt-3.5-turbo-1106",
        temperature=0.0
    )
    
    response = await chain.ainvoke({
        "role": "Python教程作者",
        "action": "解释",
        "topic": "Python中的装饰器"
    })
    
    logger.info(f"链响应: {response[:100]}...")  # 只显示前100个字符


async def main():
    """主函数"""
    logger.info("TaskFlow LLM使用示例")
    
    try:
        # 演示1: 直接调用LLM实例
        await example_direct_llm_calls()
        
        # 演示2: 高级LLM用法
        await example_advanced_llm_usage()
        
        # 演示3: 使用LLM链
        await example_chain_usage()
        
    except Exception as e:
        logger.error(f"运行示例时出错: {e}", exc_info=True)
    
    logger.info("示例完成")


if __name__ == "__main__":
    asyncio.run(main()) 