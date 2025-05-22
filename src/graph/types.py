# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import operator
from typing import Annotated

from langgraph.graph import MessagesState

from src.prompts.planner_model import Plan


class State(MessagesState):
    """State for the agent system, extends MessagesState with next field."""

    # Runtime Variables
    locale: str = "en-US"
    observations: list[str] = []
    plan_iterations: int = 0
    current_plan: Plan | str = None
    final_report: str = ""
    auto_accepted_plan: bool = False
    enable_background_investigation: bool = True
    background_investigation_results: str = None
    objectives: []
    current_objective: {}
    objective_id: str = None
    sufficiency_loop_count: int = 0
    tasks: []
    task_ids: []
    step_ids: []
    objective_results: []
    objectives_processed: int = 0
    pending_research_tasks: []
    completed_research_tasks: []
    current_task_index: int = 0
    forced_complete: bool = False
    research_loop_count: int = 0
    processing_complete: bool = False
    all_processed_results: [] 
    quality_passed: bool = False