# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""TaskFlow API模块。

该模块提供TaskFlow系统的RESTful API服务。
"""

import logging

from .app import app as api_app

# 为了兼容性，也将api_app暴露为app
app = api_app

logger = logging.getLogger(__name__)
logger.info("TaskFlow API模块已加载")

__all__ = ["api_app", "app"] 