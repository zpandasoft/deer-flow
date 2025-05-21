import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# MySQL数据库配置
def get_db_config():
    """获取MySQL数据库配置，优先从环境变量加载，如无则使用默认值"""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "deerflow"),
        "password": os.getenv("DB_PASSWORD", "deerflow_password"),
        "database": os.getenv("DB_DATABASE", "deerflow"),
        "port": int(os.getenv("DB_PORT", "3306"))
    } 