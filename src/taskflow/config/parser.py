# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow配置解析器模块。

提供解析各种配置格式的功能，如JDBC URL。
"""

import logging
import re
from typing import Dict, Optional, Tuple
from urllib.parse import quote_plus

# 获取日志记录器
logger = logging.getLogger(__name__)


def parse_jdbc_url(jdbc_url: str) -> Dict[str, str]:
    """
    解析JDBC URL为组件部分。
    
    支持格式: 
    - jdbc:mysql://host:port/database
    - jdbc:mysql://host:port/database?param1=value1&param2=value2
    - jdbc:mysql://username:password@host:port/database
    
    Args:
        jdbc_url: JDBC格式的URL
        
    Returns:
        包含分解部分的字典
    
    Raises:
        ValueError: 如果URL格式无效
    """
    # 验证基本格式
    if not jdbc_url or not jdbc_url.startswith("jdbc:"):
        raise ValueError("无效的JDBC URL格式，必须以'jdbc:'开头")
    
    # 提取数据库类型
    db_type_match = re.match(r"jdbc:([^:]+):", jdbc_url)
    if not db_type_match:
        raise ValueError("无法从JDBC URL中提取数据库类型")
    
    db_type = db_type_match.group(1)
    
    # 移除jdbc:type:前缀，获取剩余部分
    remaining = jdbc_url[len(f"jdbc:{db_type}:"):]
    
    # 检查是否有认证信息
    user = None
    password = None
    
    if "@" in remaining:
        auth_part, remaining = remaining.split("@", 1)
        if ":" in auth_part:
            user, password = auth_part.split(":", 1)
    
    # 解析主机和端口
    host_port_match = re.match(r"//([^:/]+)(?::(\d+))?/", remaining)
    if not host_port_match:
        raise ValueError("无法从JDBC URL中提取主机和端口")
    
    host = host_port_match.group(1)
    port = host_port_match.group(2) or get_default_port(db_type)
    
    # 提取数据库名和参数
    db_params_match = re.match(r"//[^/]+/([^?]+)(?:\?(.+))?", remaining)
    if not db_params_match:
        raise ValueError("无法从JDBC URL中提取数据库名")
    
    database = db_params_match.group(1)
    params_str = db_params_match.group(2) or ""
    
    # 解析参数
    params = {}
    if params_str:
        for param in params_str.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                params[key] = value
    
    # 构建结果
    result = {
        "db_type": db_type,
        "host": host,
        "port": port,
        "database": database,
        "params": params
    }
    
    if user:
        result["user"] = user
    
    if password:
        result["password"] = password
    
    return result


def get_default_port(db_type: str) -> str:
    """
    根据数据库类型获取默认端口。
    
    Args:
        db_type: 数据库类型
        
    Returns:
        默认端口字符串
    """
    defaults = {
        "mysql": "3306",
        "postgresql": "5432",
        "oracle": "1521",
        "sqlserver": "1433",
        "sqlite": "",  # SQLite没有端口
    }
    
    return defaults.get(db_type.lower(), "")


def build_sqlalchemy_url(
    driver: str,
    user: Optional[str],
    password: Optional[str],
    host: str,
    port: str,
    database: str,
    params: Optional[Dict[str, str]] = None
) -> str:
    """
    构建SQLAlchemy兼容的数据库URL。
    
    Args:
        driver: SQLAlchemy驱动名称
        user: 用户名
        password: 密码
        host: 主机名
        port: 端口
        database: 数据库名
        params: 连接参数字典
        
    Returns:
        SQLAlchemy兼容的URL字符串
    """
    # 构建基本URL
    if user and password:
        # 转义密码和用户名中的特殊字符
        escaped_user = quote_plus(user)
        escaped_password = quote_plus(password)
        auth_part = f"{escaped_user}:{escaped_password}@"
    elif user:
        escaped_user = quote_plus(user)
        auth_part = f"{escaped_user}@"
    else:
        auth_part = ""
    
    # 构建基本URL
    url = f"{driver}://{auth_part}{host}:{port}/{database}"
    
    # 添加参数
    if params and len(params) > 0:
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{param_str}"
    
    return url


def jdbc_to_sqlalchemy_url(jdbc_url: str, driver_mapping: Optional[Dict[str, str]] = None) -> str:
    """
    将JDBC URL转换为SQLAlchemy URL。
    
    Args:
        jdbc_url: JDBC格式的URL
        driver_mapping: 数据库类型到SQLAlchemy驱动的映射
        
    Returns:
        SQLAlchemy兼容的URL字符串
    """
    # 默认驱动映射
    default_mapping = {
        "mysql": "mysql+pymysql",
        "postgresql": "postgresql+psycopg2",
        "oracle": "oracle+cx_oracle",
        "sqlserver": "mssql+pyodbc",
        "sqlite": "sqlite",
    }
    
    # 使用提供的映射或默认值
    mapping = driver_mapping or default_mapping
    
    # 解析JDBC URL
    jdbc_parts = parse_jdbc_url(jdbc_url)
    
    # 获取适当的驱动
    db_type = jdbc_parts["db_type"]
    driver = mapping.get(db_type.lower())
    
    if not driver:
        logger.warning(f"未知的数据库类型 '{db_type}'，使用原始类型作为驱动")
        driver = db_type
    
    # MySQL 参数映射和转换
    params = jdbc_parts.get("params", {}).copy()
    if db_type.lower() == "mysql" and params:
        # 将 MySQL 特有参数转换为 SQLAlchemy 支持的格式
        param_mapping = {
            "serverTimezone": "time_zone",
            "useSSL": None,  # 移除SSL参数，避免解析问题
            "useLegacyDatetimeCode": None,  # 移除不支持的参数
            "characterEncoding": "charset"
        }
        
        # 应用映射
        new_params = {}
        for key, value in params.items():
            if key in param_mapping:
                if param_mapping[key] is not None:
                    new_params[param_mapping[key]] = value
            else:
                new_params[key] = value
        
        params = new_params
    
    # 构建SQLAlchemy URL
    return build_sqlalchemy_url(
        driver=driver,
        user=jdbc_parts.get("user"),
        password=jdbc_parts.get("password"),
        host=jdbc_parts["host"],
        port=jdbc_parts["port"],
        database=jdbc_parts["database"],
        params=params
    ) 