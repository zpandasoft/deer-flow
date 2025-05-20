# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""TaskFlow API应用入口。

配置FastAPI应用，注册路由，设置中间件和异常处理。
"""

import time
from datetime import datetime
from typing import Callable

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.taskflow.api.endpoints import objectives, tasks, workflows, scheduler, multiagent
from src.taskflow.api.schemas import ErrorResponse

# 创建FastAPI应用
app = FastAPI(
    title="TaskFlow API",
    description="DeerFlow任务调度与目标管理系统API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由器
app.include_router(objectives.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")
app.include_router(scheduler.router, prefix="/api/v1")
app.include_router(multiagent.router, prefix="/api/v1/multiagent")


# 请求处理中间件
@app.middleware("http")
async def add_process_time_header(request: Request, call_next: Callable):
    """添加请求处理时间头。
    
    Args:
        request: HTTP请求
        call_next: 下一个处理函数
        
    Returns:
        响应对象
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# 全局异常处理
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """处理HTTP异常。
    
    Args:
        request: HTTP请求
        exc: HTTP异常
        
    Returns:
        标准错误响应
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            error_code=f"HTTP_{exc.status_code}",
            timestamp=datetime.now(),
        ).dict(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证异常。
    
    Args:
        request: HTTP请求
        exc: 验证异常
        
    Returns:
        标准错误响应
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            detail=str(exc),
            error_code="VALIDATION_ERROR",
            timestamp=datetime.now(),
        ).dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理一般异常。
    
    Args:
        request: HTTP请求
        exc: 异常
        
    Returns:
        标准错误响应
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            detail="服务器内部错误",
            error_code="INTERNAL_ERROR",
            timestamp=datetime.now(),
        ).dict(),
    )


# 健康检查
@app.get("/health", tags=["health"])
async def health_check():
    """健康检查端点。
    
    Returns:
        健康状态
    """
    return {"status": "ok", "timestamp": datetime.now().isoformat()} 