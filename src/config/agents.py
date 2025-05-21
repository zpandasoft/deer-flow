# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from typing import Literal

# Define available LLM types
LLMType = Literal["basic", "reasoning", "vision"]

# Define agent-LLM mapping
AGENT_LLM_MAP: dict[str, LLMType] = {
    "coordinator": "basic",
    "planner": "basic",
    "researcher": "basic",
    "coder": "basic",
    "reporter": "basic",
    "podcast_script_writer": "basic",
    "ppt_composer": "basic",
    "prose_writer": "basic",
    "context_analyzer": "basic",
    "objective_decomposer": "basic",
    "task_analyzer": "basic",
    "processing": "basic",
    "synthesis": "basic",
    "quality_evaluator": "basic",
    "sufficiency_evaluator": "basic",
    "error_handler": "basic",
    "human_interaction": "basic"
}
