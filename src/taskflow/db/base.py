# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow数据库基础模块。

提供数据库基础设施，包括基类、会话工厂和元数据。
"""

import logging
from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from src.taskflow.config.settings import settings
from src.taskflow.exceptions import DatabaseError

# 获取日志记录器
logger = logging.getLogger(__name__)

# 创建基类
Base = declarative_base()

# 创建元数据对象
metadata = MetaData()

# 创建引擎
engine = create_engine(
    settings.database.sqlalchemy_url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_recycle=settings.database.pool_recycle,
    pool_pre_ping=True,  # 连接前检查
    echo=settings.debug,  # 调试模式下输出SQL
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Session:
    """
    获取数据库会话对象。
    
    Returns:
        Session: 数据库会话对象
    """
    return SessionLocal()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    数据库会话上下文管理器。
    
    Yields:
        Session: 数据库会话对象
        
    Raises:
        DatabaseError: 数据库操作错误
    """
    session = get_db_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"数据库操作失败: {str(e)}")
        raise DatabaseError(f"数据库操作失败: {str(e)}") from e
    finally:
        session.close()


def init_db() -> None:
    """
    初始化数据库，创建所有表。
    
    谨慎使用，会删除现有数据。
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("数据库已初始化并创建所有表")


def create_tables() -> None:
    """
    创建所有表，如果不存在的话。
    
    不会删除现有数据。
    """
    Base.metadata.create_all(bind=engine)
    logger.info("确保所有数据库表已创建") 