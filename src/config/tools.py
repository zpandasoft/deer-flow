# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import os
import enum
from dotenv import load_dotenv

load_dotenv()


class SearchEngine(enum.Enum):
    TAVILY = "tavily"
    DUCKDUCKGO = "duckduckgo"
    BRAVE_SEARCH = "brave_search"
    ARXIV = "arxiv"


# Tool configuration
SELECTED_SEARCH_ENGINE = SearchEngine.DUCKDUCKGO.value  # Force using DuckDuckGo regardless of env var
SEARCH_MAX_RESULTS = 3
