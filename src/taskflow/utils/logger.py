# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow日志工具模块。

提供统一的日志配置和获取函数，支持结构化日志和上下文追踪。
"""

import logging
import os
import sys
import time
import uuid
import traceback
import threading
from datetime import datetime
from functools import wraps
from typing import Any, Dict, Optional, Callable, TypeVar, cast
from pathlib import Path

from pythonjsonlogger import jsonlogger

# 类型变量
F = TypeVar('F', bound=Callable[..., Any])

# 默认日志格式
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 日志目录
LOG_DIR = Path(__file__).absolute().parent.parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 默认JSON日志格式
JSON_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(user_id)s %(trace_id)s %(context)s %(duration_ms)s %(exception)s %(exception_traceback)s"

# 线程本地存储，用于存储请求上下文
_thread_local = threading.local()


class RequestContext:
    """请求上下文类，用于存储请求相关信息"""
    
    def __init__(self, request_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        初始化请求上下文。
        
        Args:
            request_id: 请求ID，如果为None则自动生成
            user_id: 用户ID
        """
        self.request_id = request_id or str(uuid.uuid4())
        self.user_id = user_id
        self.trace_id = str(uuid.uuid4())
        self.context: Dict[str, Any] = {}
        self.start_time = time.time()
    
    def add_context(self, key: str, value: Any) -> None:
        """
        添加上下文信息。
        
        Args:
            key: 键
            value: 值
        """
        self.context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """
        获取上下文信息。
        
        Args:
            key: 键
            default: 默认值
            
        Returns:
            上下文值或默认值
        """
        return self.context.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典。
        
        Returns:
            包含上下文信息的字典
        """
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "trace_id": self.trace_id,
            "context": self.context,
            "duration_ms": int((time.time() - self.start_time) * 1000)
        }


def get_current_context() -> Optional[RequestContext]:
    """
    获取当前线程的请求上下文。
    
    Returns:
        请求上下文或None（如果不存在）
    """
    return getattr(_thread_local, "request_context", None)


def set_current_context(context: RequestContext) -> None:
    """
    设置当前线程的请求上下文。
    
    Args:
        context: 请求上下文
    """
    _thread_local.request_context = context


def clear_current_context() -> None:
    """清除当前线程的请求上下文。"""
    if hasattr(_thread_local, "request_context"):
        delattr(_thread_local, "request_context")


def with_request_context(func: F) -> F:
    """
    请求上下文装饰器，确保函数执行期间存在请求上下文。
    
    Args:
        func: 要装饰的函数
        
    Returns:
        装饰后的函数
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 检查是否已存在上下文
        context = get_current_context()
        created_context = False
        
        # 如果不存在，创建新上下文
        if context is None:
            context = RequestContext()
            set_current_context(context)
            created_context = True
        
        try:
            return func(*args, **kwargs)
        finally:
            # 如果是我们创建的上下文，清除它
            if created_context:
                clear_current_context()
    
    return cast(F, wrapper)


class ContextAwareJsonFormatter(jsonlogger.JsonFormatter):
    """支持上下文的JSON日志格式化器"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """
        添加字段到日志记录。
        
        Args:
            log_record: 日志记录字典
            record: 日志记录对象
            message_dict: 消息字典
        """
        super().add_fields(log_record, record, message_dict)
        
        # 添加时间戳
        log_record["timestamp"] = datetime.utcnow().isoformat()
        
        # 添加上下文信息（如果存在）
        context = get_current_context()
        if context:
            log_record.update({
                "request_id": context.request_id,
                "user_id": context.user_id,
                "trace_id": context.trace_id,
                "context": context.context,
                "duration_ms": int((time.time() - context.start_time) * 1000)
            })
        else:
            log_record.update({
                "request_id": None,
                "user_id": None,
                "trace_id": None,
                "context": {},
                "duration_ms": None
            })
        
        # 处理异常信息
        if record.exc_info:
            log_record["exception"] = str(record.exc_info[1])
            log_record["exception_traceback"] = "".join(traceback.format_exception(*record.exc_info))


class ContextFilter(logging.Filter):
    """日志上下文过滤器，添加上下文信息到日志记录"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录，添加上下文信息。
        
        Args:
            record: 日志记录
            
        Returns:
            True表示包含此记录
        """
        context = get_current_context()
        if context:
            record.request_id = context.request_id
            record.user_id = context.user_id
            record.trace_id = context.trace_id
            record.context = str(context.context)
            record.duration_ms = int((time.time() - context.start_time) * 1000)
        else:
            record.request_id = ""
            record.user_id = ""
            record.trace_id = ""
            record.context = "{}"
            record.duration_ms = 0
        
        # 转换异常信息
        if record.exc_info:
            record.exception = str(record.exc_info[1])
            record.exception_traceback = "".join(traceback.format_exception(*record.exc_info))
        else:
            record.exception = ""
            record.exception_traceback = ""
        
        return True


def get_logger(
    name: str, 
    level: Optional[int] = None, 
    use_json: bool = True, 
    log_to_file: bool = False,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 10
) -> logging.Logger:
    """
    获取配置好的日志记录器。
    
    Args:
        name: 记录器名称
        level: 日志级别，默认为None（使用环境变量或INFO级别）
        use_json: 是否使用JSON格式，默认为True
        log_to_file: 是否同时记录到文件，默认为False
        max_file_size: 日志文件最大大小，默认为10MB
        backup_count: 保留的日志文件数量，默认为10
    
    Returns:
        配置好的日志记录器
    """
    # 确定日志级别
    if level is None:
        log_level_str = os.environ.get("LOG_LEVEL", "INFO")
        level = getattr(logging, log_level_str, logging.INFO)
    
    # 获取日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 如果已经有处理器，则直接返回
    if logger.handlers:
        return logger
    
    # 添加上下文过滤器
    context_filter = ContextFilter()
    logger.addFilter(context_filter)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    
    # 设置格式
    if use_json:
        formatter = ContextAwareJsonFormatter(JSON_FORMAT)
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s - "
            "[request_id=%(request_id)s user_id=%(user_id)s trace_id=%(trace_id)s]"
        )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 如果需要同时记录到文件
    if log_to_file:
        from logging.handlers import RotatingFileHandler
        
        log_file = LOG_DIR / f"{name.replace('.', '_')}.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_file_size,
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def log_execution_time(logger: logging.Logger, level: int = logging.INFO):
    """
    记录函数执行时间的装饰器。
    
    Args:
        logger: 日志记录器
        level: 日志级别
        
    Returns:
        装饰器函数
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.log(level, f"函数 {func.__name__} 执行完成", extra={
                    "duration_ms": int(execution_time * 1000),
                    "function": func.__name__
                })
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.exception(f"函数 {func.__name__} 执行出错: {str(e)}", extra={
                    "duration_ms": int(execution_time * 1000),
                    "function": func.__name__
                })
                raise
        return cast(F, wrapper)
    return decorator 