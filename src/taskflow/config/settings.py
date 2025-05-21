# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow配置设置模块。

管理系统配置、环境变量和默认值。
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from dotenv import load_dotenv
from pydantic import Field, validator
from pydantic_settings import BaseSettings

from src.taskflow.config.parser import jdbc_to_sqlalchemy_url
from src.taskflow.config.loader import find_and_load_config

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
        
        # 尝试从JDBC URL生成SQLAlchemy URL
        jdbc_url = values.get("jdbc_url", "")
        if jdbc_url:
            logger.info(f"使用JDBC URL: {jdbc_url}")
            return jdbc_to_sqlalchemy_url(jdbc_url)
        
        # 如果没有JDBC URL，回退到SQLite
        logger.warning("未找到有效的数据库配置，使用SQLite作为后备选项")
        sqlite_path = str(ROOT_DIR / "taskflow.db")
        return f"sqlite:///{sqlite_path}"


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
    
    # 默认模型配置
    model_type: str = Field(default="openai", env="LLM_MODEL_TYPE")
    model_name: str = Field(default="gpt-4", env="LLM_MODEL_NAME")
    temperature: float = Field(default=0.0, env="LLM_TEMPERATURE")
    max_tokens: int = Field(default=4000, env="LLM_MAX_TOKENS")
    api_key: str = Field(default="", env="LLM_API_KEY")
    api_base: str = Field(default="", env="LLM_API_BASE")
    
    # 缓存配置
    use_cache: bool = Field(default=True, env="LLM_USE_CACHE")
    
    model_config = {
        "env_prefix": "LLM_",
        "env_file": ".env",
        "extra": "ignore"
    }
    
    def _load_llm_config(self) -> Dict[str, Any]:
        """
        加载LLM配置。
        
        尝试从conf.yaml加载配置，如果不存在则返回空字典。
        
        Returns:
            LLM配置字典
        """
        config = find_and_load_config("conf.yaml")
        if not config:
            logger.warning("未找到conf.yaml配置文件，将使用默认配置")
        return config
    
    def get_llm_config_by_type(self, llm_type: str) -> Dict[str, Any]:
        """
        根据LLM类型获取配置。
        
        Args:
            llm_type: LLM类型
            
        Returns:
            LLM配置字典
        """
        # LLM类型到配置键的映射
        type_to_config = {
            "basic": "BASIC_MODEL",
            "reasoning": "REASONING_MODEL",
            "vision": "VISION_MODEL",
            "coding": "CODING_MODEL",
            "planning": "PLANNING_MODEL",
        }
        
        # 获取配置键
        config_key = type_to_config.get(llm_type, "BASIC_MODEL")
        
        # 加载配置
        config = self._load_llm_config()
        
        # 从配置中获取对应类型的LLM配置
        llm_config = config.get(config_key)
        
        # 如果不存在该类型的配置，使用基础模型配置
        if not llm_config:
            logger.warning(f"未找到类型 {llm_type} 的LLM配置，使用基础模型配置")
            llm_config = config.get("BASIC_MODEL", {})
        
        # 如果配置中没有获取到任何信息，使用默认值
        if not llm_config:
            llm_config = {
                "model": self.model_name,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "api_key": self.api_key,
                "base_url": self.api_base,
            }
        
        return llm_config
    
    def get_provider_for_agent(self, agent_type: str) -> str:
        """
        根据智能体类型获取LLM提供者类型。
        
        Args:
            agent_type: 智能体类型
            
        Returns:
            LLM提供者类型
        """
        # 所有智能体默认使用OpenAI提供者
        # 可以后续根据需要调整不同智能体使用不同的LLM提供者
        agent_to_provider = {
            # 示例: 特定智能体类型对应特定提供者
            # "research": "anthropic",
            # "planning": "azure",
        }
        
        # 获取提供者类型
        provider_type = agent_to_provider.get(agent_type, self.model_type)
        
        logger.info(f"为智能体 {agent_type} 选择LLM提供者: {provider_type}")
        return provider_type
        
    def get_provider_for_task(self, task_type: str) -> str:
        """
        根据任务类型获取LLM提供者类型。
        
        Args:
            task_type: 任务类型
            
        Returns:
            LLM提供者类型
        """
        # 所有任务默认使用OpenAI提供者
        # 可以后续根据需要调整不同任务使用不同的LLM提供者
        task_to_provider = {
            # 示例: 特定任务类型对应特定提供者
            # "coding": "anthropic",
            # "reasoning": "azure",
        }
        
        # 获取提供者类型
        provider_type = task_to_provider.get(task_type, self.model_type)
        
        logger.info(f"为任务 {task_type} 选择LLM提供者: {provider_type}")
        return provider_type
        
    def get_provider_settings(self, provider_type: str) -> "LLMProviderSettings":
        """
        根据提供者类型获取LLM提供者配置。
        
        Args:
            provider_type: 提供者类型
            
        Returns:
            LLM提供者配置
        """
        # 默认使用基础模型配置
        basic_config = self.get_llm_config_by_type("basic")
        
        # 创建提供者设置
        provider_settings = LLMProviderSettings(
            provider_type=provider_type,
            model_name=basic_config.get("model", self.model_name),
            temperature=basic_config.get("temperature", self.temperature),
            max_tokens=basic_config.get("max_tokens", self.max_tokens),
            api_key=basic_config.get("api_key", self.api_key),
            api_base=basic_config.get("base_url", self.api_base),
            parameters={}
        )
        
        logger.info(f"为提供者 {provider_type} 创建配置: model={provider_settings.model_name}")
        return provider_settings
    
    @property
    def default_provider(self) -> str:
        """默认LLM提供者类型"""
        return self.model_type


class LLMProviderSettings:
    """LLM提供者配置设置"""
    
    def __init__(
        self,
        provider_type: str,
        model_name: str,
        temperature: float,
        max_tokens: int,
        api_key: str,
        api_base: str,
        parameters: Dict[str, Any] = None
    ):
        """
        初始化LLM提供者配置设置。
        
        Args:
            provider_type: 提供者类型
            model_name: 模型名称
            temperature: 温度参数
            max_tokens: 最大令牌数
            api_key: API密钥
            api_base: API基础URL
            parameters: 其他参数
        """
        self.provider_type = provider_type
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key
        self.api_base = api_base
        self.parameters = parameters or {}


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
    
    # 记录 LLM 配置摘要
    basic_config = settings.llm.get_llm_config_by_type("basic")
    config_keys = ["model", "temperature", "max_tokens"]
    config_summary = ", ".join([f"{k}={basic_config.get(k)}" for k in config_keys if k in basic_config])
    logger.info(f"LLM基础配置: {config_summary}") 