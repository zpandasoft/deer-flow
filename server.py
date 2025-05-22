# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
Server script for running the DeerFlow API.
"""

import argparse
import logging
import os

import uvicorn

# 创建日志目录（如果不存在）
os.makedirs("logs", exist_ok=True)

# 配置详细的日志记录
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        # 控制台输出
        logging.StreamHandler(),
        # 文件输出 - 按日期滚动
        logging.FileHandler(f"logs/deerflow_{os.path.basename(__file__).split('.')[0]}.log"),
    ]
)

# 为关键模块设置更详细的日志级别
logging.getLogger("deerflow").setLevel(logging.DEBUG)
logging.getLogger("deerflow.llm").setLevel(logging.DEBUG)
logging.getLogger("deerflow.context_analyzer").setLevel(logging.DEBUG)
logging.getLogger("deerflow.decorators").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the DeerFlow API server")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (default: True except on Windows)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind the server to (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level (default: info)",
    )

    args = parser.parse_args()

    # Determine reload setting
    reload = False

    # Command line arguments override defaults
    if args.reload:
        reload = True

    # 根据命令行参数设置日志级别
    if args.log_level == "debug":
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)
        # 为所有deerflow模块设置DEBUG级别
        logging.getLogger("deerflow").setLevel(logging.DEBUG)

    logger.info("Starting DeerFlow API server")
    uvicorn.run(
        "src.server.app:app",
        host=args.host,
        port=args.port,
        reload=reload,
        log_level=args.log_level,
    )
