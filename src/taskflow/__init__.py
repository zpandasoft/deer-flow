# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
DeerFlow任务调度与目标管理系统。

该系统提供分解复杂研究目标、管理任务执行流程，
并通过多智能体协作完成目标的能力。
"""

import logging
from pathlib import Path

# 设置基本日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# 包路径
PACKAGE_ROOT = Path(__file__).parent.absolute()

# 版本
__version__ = "0.1.0"

def register_taskflow():
    """注册任务流系统，初始化必要的组件。"""
    from src.taskflow.db.service import init_database
    
    # 初始化数据库
    init_database()
    
    # 在此添加其他初始化代码
    
    logging.info("TaskFlow系统已注册和初始化")
    return True 