# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow配置设置模块。

管理系统配置、环境变量和默认值。
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from pydantic import Field, validator
from pydantic_settings import BaseSettings

from src.taskflow.config.parser import jdbc_to_sqlalchemy_url

# 获取日志记录器
logger = logging.getLogger(__name__)

# 加载.env文件
load_dotenv()

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent.parent.absolute()


class DatabaseSettings(BaseSettings):
    """数据库配置设置"""
    
    # 从jdbc.url解析的数据库连接信息
    jdbc_url: str = Field(
        default=os.getenv("jdbc.url", ""),
        description="JDBC格式的数据库连接URL"
    )
    
    # 提取的数据库信息，供SQLAlchemy使用
    db_host: str = ""
    db_port: int = 3306
    db_name: str = ""
    db_user: str = ""
    db_password: str = ""
    db_driver: str = "mysql+pymysql"
    
    # SQL连接池配置
    pool_size: int = Field(default=5, env="DB_POOL_SIZE")
    max_overflow: int = Field(default=10, env="DB_MAX_OVERFLOW")
    pool_recycle: int = Field(default=3600, env="DB_POOL_RECYCLE")  # 1小时
    
    # SQLAlchemy URL
    sqlalchemy_url: str = ""
    
    model_config = {
        "env_prefix": "DB_",
        "env_file": ".env",
        "extra": "ignore"
    }
    
    @validator("sqlalchemy_url", pre=True, always=True)
    def assemble_sqlalchemy_url(cls, v, values):
        """从JDBC URL生成SQLAlchemy URL，或使用已有值"""
        if v:
            return v
        
        jdbc_url = values.get("jdbc_url")
        if not jdbc_url:
            logger.warning("未提供jdbc.url或DB_SQLALCHEMY_URL，数据库连接可能不可用")
            return ""
        
        try:
            # 使用配置解析器从JDBC URL构建SQLAlchemy URL
            return jdbc_to_sqlalchemy_url(jdbc_url)
        except Exception as e:
            logger.error(f"解析JDBC URL时出错: {str(e)}")
            raise ValueError(f"无法从JDBC URL构建SQLAlchemy URL: {str(e)}")


class APISettings(BaseSettings):
    """API服务配置设置"""
    
    host: str = Field(default="0.0.0.0", env="API_HOST")
    port: int = Field(default=8000, env="API_PORT")
    reload: bool = Field(default=False, env="API_RELOAD")
    debug: bool = Field(default=False, env="API_DEBUG")
    
    # 安全设置
    enable_auth: bool = Field(default=True, env="API_ENABLE_AUTH")
    jwt_secret_key: str = Field(default="", env="API_JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", env="API_JWT_ALGORITHM")
    token_expire_minutes: int = Field(default=60 * 24, env="API_TOKEN_EXPIRE_MINUTES")  # 24小时
    
    model_config = {
        "env_prefix": "API_",
        "env_file": ".env",
        "extra": "ignore"
    }
    
    @validator("jwt_secret_key", pre=True, always=True)
    def check_jwt_secret(cls, v, values):
        """验证JWT密钥"""
        enable_auth = values.get("enable_auth")
        if enable_auth and not v:
            import secrets
            generated_key = secrets.token_hex(32)
            logger.warning(f"未设置API_JWT_SECRET，已自动生成临时密钥。为了安全起见，请在.env文件中设置此值。")
            return generated_key
        return v


class SchedulerSettings(BaseSettings):
    """任务调度器配置设置"""
    
    worker_count: int = Field(default=5, env="SCHEDULER_WORKER_COUNT")
    queue_size: int = Field(default=100, env="SCHEDULER_QUEUE_SIZE")
    default_timeout: int = Field(default=300, env="SCHEDULER_DEFAULT_TIMEOUT")  # 5分钟
    heartbeat_interval: int = Field(default=30, env="SCHEDULER_HEARTBEAT_INTERVAL")  # 30秒
    
    model_config = {
        "env_prefix": "SCHEDULER_",
        "env_file": ".env",
        "extra": "ignore"
    }


class LLMSettings(BaseSettings):
    """LLM配置设置"""
    
    model_type: str = Field(default="openai", env="LLM_MODEL_TYPE")
    model_name: str = Field(default="gpt-4", env="LLM_MODEL_NAME")
    temperature: float = Field(default=0.0, env="LLM_TEMPERATURE")
    max_tokens: int = Field(default=4000, env="LLM_MAX_TOKENS")
    api_key: str = Field(default="", env="LLM_API_KEY")
    api_base: str = Field(default="", env="LLM_API_BASE")
    
    model_config = {
        "env_prefix": "LLM_",
        "env_file": ".env",
        "extra": "ignore"
    }


class Settings(BaseSettings):
    """系统总体配置设置"""
    
    # 应用程序设置
    app_name: str = Field(default="DeerFlow TaskFlow", env="APP_NAME")
    env: str = Field(default="development", env="APP_ENV")
    debug: bool = Field(default=False, env="APP_DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # 子配置
    database: DatabaseSettings = DatabaseSettings()
    api: APISettings = APISettings()
    scheduler: SchedulerSettings = SchedulerSettings()
    llm: LLMSettings = LLMSettings()
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """验证日志级别是否有效"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            logger.warning(f"无效的日志级别 '{v}'，使用默认值 'INFO'")
            return "INFO"
        return v


# 创建全局配置实例
settings = Settings()

# 调试日志
if settings.debug:
    logger.info(f"配置已加载: 环境={settings.env}, 调试模式={settings.debug}, 数据库URL={settings.database.sqlalchemy_url}")
    
    if settings.database.jdbc_url:
        logger.info(f"JDBC URL: {settings.database.jdbc_url}")
    else:
        logger.warning("未配置JDBC URL，使用直接的SQLAlchemy URL") 