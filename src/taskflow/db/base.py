# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow数据库基础模块。

提供数据库基础设施，包括基类、会话工厂和元数据。
"""

import logging
from contextlib import contextmanager, asynccontextmanager
from typing import Any, Generator, AsyncGenerator

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_scoped_session
import asyncio
import re

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

# 创建异步引擎 - 仅当数据库支持异步操作时
async_engine = None
AsyncSessionLocal = None

# 检查数据库类型
if "sqlite" not in settings.database.sqlalchemy_url:
    # 将MySQL URL转换为异步格式
    async_sqlalchemy_url = settings.database.sqlalchemy_url.replace('mysql+pymysql', 'mysql+aiomysql')
    # 如果URL包含ssl=false，移除整个ssl参数
    if 'ssl=false' in async_sqlalchemy_url or 'ssl=true' in async_sqlalchemy_url:
        # 找到ssl参数
        async_sqlalchemy_url = re.sub(r'&?ssl=(false|true)(&|$)', r'\2', async_sqlalchemy_url)
        # 修复连续的&符号
        async_sqlalchemy_url = async_sqlalchemy_url.replace('&&', '&')
        # 修复结尾的&符号
        if async_sqlalchemy_url.endswith('&'):
            async_sqlalchemy_url = async_sqlalchemy_url[:-1]
    
    # 创建异步引擎
    async_engine = create_async_engine(
        async_sqlalchemy_url,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_recycle=settings.database.pool_recycle,
        pool_pre_ping=True,
        echo=settings.debug,
    )
    
    # 创建异步会话工厂
    AsyncSessionLocal = sessionmaker(
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        bind=async_engine
    )


def get_db_session() -> Session:
    """
    获取数据库会话对象。
    
    Returns:
        Session: 数据库会话对象
    """
    return SessionLocal()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取异步数据库会话对象。
    
    Yields:
        AsyncSession: 异步数据库会话对象
        
    Raises:
        NotImplementedError: 当数据库不支持异步操作时
    """
    if AsyncSessionLocal is None:
        raise NotImplementedError("当前数据库配置不支持异步操作")
        
    async_session = AsyncSessionLocal()
    try:
        yield async_session
    finally:
        await async_session.close()


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


@asynccontextmanager
async def async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    异步数据库会话上下文管理器。
    
    Yields:
        AsyncSession: 异步数据库会话对象
        
    Raises:
        DatabaseError: 数据库操作错误
    """
    async_session = AsyncSessionLocal()
    try:
        yield async_session
        await async_session.commit()
    except Exception as e:
        await async_session.rollback()
        logger.error(f"异步数据库操作失败: {str(e)}")
        raise DatabaseError(f"异步数据库操作失败: {str(e)}") from e
    finally:
        await async_session.close()


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