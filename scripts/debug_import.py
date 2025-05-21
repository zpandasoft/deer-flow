#!/usr/bin/env python
# encoding: utf-8

import os
import sys
import inspect

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("Python路径:")
for path in sys.path:
    print(f"  - {path}")

print("\n尝试导入src包:")
import src
print(f"src.__file__: {src.__file__}")

print("\n尝试直接导入config.py:")
try:
    from src import config
    print(f"config.__file__: {config.__file__}")
    print(f"config模块属性: {dir(config)}")
    print(f"config模块类型: {type(config)}")
    print(f"config模块源码: {inspect.getsource(config) if hasattr(config, '__file__') else '无法获取源码'}")
except Exception as e:
    print(f"导入错误: {e}")

print("\n尝试导入config包:")
try:
    import src.config
    print(f"src.config.__file__: {src.config.__file__}")
    print(f"src.config模块属性: {dir(src.config)}")
except Exception as e:
    print(f"导入错误: {e}")

print("\n尝试使用importlib导入:")
import importlib.util
try:
    spec = importlib.util.spec_from_file_location("config", os.path.join(os.path.dirname(src.__file__), "config.py"))
    if spec and spec.loader:
        config_direct = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_direct)
        print(f"直接导入config.py成功")
        print(f"config_direct属性: {dir(config_direct)}")
        if hasattr(config_direct, 'get_db_config'):
            print(f"找到get_db_config函数")
        else:
            print(f"未找到get_db_config函数")
    else:
        print("无法加载config.py模块规范")
except Exception as e:
    print(f"importlib导入错误: {e}") 