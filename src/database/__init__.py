from src.config import get_db_config
from .mysql_service import MySQLService

# 全局数据库服务实例
db_service = None

def init_db_connection():
    """初始化数据库连接"""
    global db_service
    if db_service is None:
        db_service = MySQLService(get_db_config())
    return db_service

def get_db_service():
    """获取数据库服务实例"""
    global db_service
    if db_service is None:
        db_service = init_db_connection()
    return db_service 