#!/usr/bin/env python
# encoding: utf-8

import os
import sys
import pymysql
import importlib.util
import getpass

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 直接导入src/config.py文件
# 注意：from src import config导入的是src/config/__init__.py而不是src/config.py
import src
import os
import mysql.connector
config_path = os.path.join(os.path.dirname(src.__file__), "config.py")
spec = importlib.util.spec_from_file_location("config_direct", config_path)
config_direct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_direct)
get_db_config = config_direct.get_db_config

def create_database_and_user():
    """创建数据库和用户"""
    config = get_db_config()
    connection = None
    
    # 获取MySQL root密码
    
    try:

        db_name = os.getenv("DB_DATABASE", "deerflow")
        db_user = os.getenv("DB_USER", "deerflow")
        db_password =os.getenv("DB_PASSWORD", "deerflow_password")
        # 使用root用户连接到MySQL
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", 3306),
            user=db_user,
            password=db_password,
            database=db_name,
            charset="utf8mb4"
        )
        

        
        with connection.cursor() as cursor:
            # 创建数据库（如果不存在）
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            
            # 创建用户（如果不存在）- MySQL 8.0+语法
            try:
                cursor.execute(f"CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{db_password}'")
            except pymysql.err.OperationalError:
                # MySQL 5.7及以下版本不支持IF NOT EXISTS语法
                try:
                    cursor.execute(f"CREATE USER '{db_user}'@'localhost' IDENTIFIED BY '{db_password}'")
                except pymysql.err.OperationalError as e:
                    if "1396" not in str(e):  # 1396是"用户已存在"的错误码
                        raise
                        
            # 授予用户权限
            cursor.execute(f"GRANT ALL PRIVILEGES ON {db_name}.* TO '{db_user}'@'localhost'")
            cursor.execute("FLUSH PRIVILEGES")
            
        connection.commit()
        print(f"数据库 '{db_name}' 和用户 '{db_user}' 创建成功")
        return True
    except Exception as e:
        print(f"创建数据库和用户时出错: {e}")
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()

def create_tables():
    """创建必要的数据库表"""
    config = get_db_config()
    connection = None
    
    try:
        # 连接到MySQL服务器（使用配置中的用户和密码）
        connection = pymysql.connect(
            host=config.get("host", "localhost"),
            user=config.get("user", "deerflow"),
            password=config.get("password", "deerflow_password"),
            database=config.get("database", "deerflow"),
            charset="utf8mb4"
        )
    
        with connection.cursor() as cursor:
            # 创建agent_llm_calls表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agent_llm_calls (
                    call_id VARCHAR(36) PRIMARY KEY,
                    agent_name VARCHAR(100) NOT NULL,
                    node_name VARCHAR(100) NOT NULL,
                    reference_id VARCHAR(36),
                    reference_type VARCHAR(20),
                    input_data LONGTEXT NOT NULL,
                    output_data LONGTEXT NOT NULL,
                    tokens_used INT,
                    duration_ms INT,
                    status VARCHAR(20) NOT NULL,
                    error_message TEXT,
                    created_at TIMESTAMP NOT NULL,
                    model_name VARCHAR(100),
                    metadata JSON
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            ''')
            
            print("数据表创建成功")
            
        connection.commit()
        return True
    except Exception as e:
        print(f"创建数据表时出错: {e}")
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    print("初始化数据库...")
    
    # 第一步：创建数据库和用户
    if create_database_and_user():
        # 第二步：创建表结构
        if create_tables():
            print("数据库初始化完成。")
        else:
            print("数据库初始化失败：表结构创建失败。")
    else:
        print("数据库初始化失败：数据库或用户创建失败。") 