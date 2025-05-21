# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from langgraph.prebuilt import create_react_agent

from src.prompts import apply_prompt_template
from src.tools import (
    crawl_tool,
    python_repl_tool,
    web_search_tool,
)

from src.llms.llm import get_llm_by_type
from src.config.agents import AGENT_LLM_MAP


# Create agents using configured LLM types
def create_agent(agent_name: str, agent_type: str, tools: list, prompt_template: str):
    """Factory function to create agents with consistent configuration."""
    return create_react_agent(
        name=agent_name,
        model=get_llm_by_type(AGENT_LLM_MAP[agent_type]),
        tools=tools,
        prompt=lambda state: apply_prompt_template(prompt_template, state),
    )


# Create agents using the factory function
research_agent = create_agent(
    "researcher", "researcher", [web_search_tool, crawl_tool], "researcher"
)
coder_agent = create_agent("coder", "coder", [python_repl_tool], "coder")

# Context Analyzer Agent
context_analyzer_agent = create_agent(
    "context_analyzer", "context_analyzer", [web_search_tool], "context_analyzer"
)

# Objective Decomposer Agent
objective_decomposer_agent = create_agent(
    "objective_decomposer", "objective_decomposer", [], "objective_decomposer"
)

# Task Analyzer Agent
task_analyzer_agent = create_agent(
    "task_analyzer", "task_analyzer", [], "task_analyzer"
)

# Processing Agent
processing_agent = create_agent(
    "processing", "processing", [], "processing"
)

# Quality Evaluator Agent
quality_evaluator_agent = create_agent(
    "quality_evaluator", "quality_evaluator", [], "quality_evaluator"
)

# Synthesis Agent
synthesis_agent = create_agent(
    "synthesis", "synthesis", [], "synthesis"
)

# Sufficiency Evaluator Agent
sufficiency_evaluator_agent = create_agent(
    "sufficiency_evaluator", "sufficiency_evaluator", [], "sufficiency_evaluator"
)

# Error Handler Agent
error_handler_agent = create_agent(
    "error_handler", "error_handler", [], "error_handler"
)

# Human Interaction Agent
human_interaction_agent = create_agent(
    "human_interaction", "human_interaction", [], "human_interaction"
)
