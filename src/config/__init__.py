# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import os
from .tools import SEARCH_MAX_RESULTS, SELECTED_SEARCH_ENGINE, SearchEngine
from .loader import load_yaml_config
from .questions import BUILT_IN_QUESTIONS, BUILT_IN_QUESTIONS_ZH_CN

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MySQL数据库配置
def get_db_config():
    """获取MySQL数据库配置，优先从环境变量加载，如无则使用默认值"""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "deerflow"),
        "password": os.getenv("DB_PASSWORD", "deerflow_password"),
        "database": os.getenv("DB_DATABASE", "deerflow"),
        "port": int(os.getenv("DB_PORT", "3306"))
    }

# Team configuration
TEAM_MEMBER_CONFIGRATIONS = {
    "researcher": {
        "name": "researcher",
        "desc": (
            "Responsible for searching and collecting relevant information, understanding user needs and conducting research analysis"
        ),
        "desc_for_llm": (
            "Uses search engines and web crawlers to gather information from the internet. "
            "Outputs a Markdown report summarizing findings. Researcher can not do math or programming."
        ),
        "is_optional": False,
    },
    "coder": {
        "name": "coder",
        "desc": (
            "Responsible for code implementation, debugging and optimization, handling technical programming tasks"
        ),
        "desc_for_llm": (
            "Executes Python or Bash commands, performs mathematical calculations, and outputs a Markdown report. "
            "Must be used for all mathematical computations."
        ),
        "is_optional": True,
    },
}

TEAM_MEMBERS = list(TEAM_MEMBER_CONFIGRATIONS.keys())

__all__ = [
    # Other configurations
    "TEAM_MEMBERS",
    "TEAM_MEMBER_CONFIGRATIONS",
    "SEARCH_MAX_RESULTS",
    "SELECTED_SEARCH_ENGINE",
    "SearchEngine",
    "BUILT_IN_QUESTIONS",
    "BUILT_IN_QUESTIONS_ZH_CN",
    "get_db_config",
]
