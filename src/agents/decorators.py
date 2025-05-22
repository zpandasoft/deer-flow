import time
import json
import functools
import logging
from typing import Callable, Dict, Any
from src.database.mysql_service import MySQLService

# 全局数据库服务实例
db_service = None
logger = logging.getLogger("src.agents.decorators")

def setup_db_service(config: Dict):
    """设置数据库服务"""
    global db_service
    db_service = MySQLService(config)

def _truncate_for_logging(data, max_length=3000):
    """截断过长的数据用于日志记录"""
    if not isinstance(data, str):
        try:
            data_str = json.dumps(data, ensure_ascii=False)
        except:
            data_str = str(data)
    else:
        data_str = data
    
    if len(data_str) > max_length:
        return data_str[:max_length] + f"... [截断，完整长度: {len(data_str)}]"
    return data_str

def log_llm_call(original_agent):
    """记录LLM调用装饰器，适用于通过工厂函数创建的智能体"""
    # 检查原始智能体的类型
    agent_type = type(original_agent).__name__
    logger.debug(f"应用log_llm_call装饰器到类型为 {agent_type} 的智能体")
    
    # 安全获取智能体名称，提供多级回退机制
    if hasattr(original_agent, "name"):
        agent_name = original_agent.name
    elif hasattr(original_agent, "__name__"):
        agent_name = original_agent.__name__
    else:
        agent_name = str(original_agent.__class__.__name__)
    
    # 如果是CompiledStateGraph类型，需要特殊处理
    if agent_type == "CompiledStateGraph":
        logger.warning(f"检测到智能体 {agent_name} 是CompiledStateGraph类型，将使用invoke方法代替直接调用")
        
        @functools.wraps(original_agent)
        def wrapper(state: Dict[str, Any], *args, **kwargs):
            global db_service
            if db_service is None:
                # 如果数据库服务未初始化，尝试初始化
                from src.config import get_db_config
                setup_db_service(get_db_config())
                
            # 获取参考ID（如果在state中有）
            reference_id = None
            reference_type = None
            
            if 'objective_id' in state:
                reference_id = state['objective_id']
                reference_type = 'OBJECTIVE'
            elif 'current_task' in state and 'id' in state['current_task']:
                reference_id = state['current_task']['id']
                reference_type = 'TASK'
            elif 'task_id' in state:
                reference_id = state['task_id']
                reference_type = 'TASK'
                
            # 记录开始时间
            start_time = time.time()
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))
            
            # 复制输入状态作为记录
            input_state = {k: v for k, v in state.items() if not k.startswith('_')}
            
            # 记录调用开始详细日志
            logger.info(f"====== 开始调用智能体 {agent_name} [使用invoke方法] ======")
            logger.info(f"调用时间: {timestamp}")
            logger.info(f"节点名称: {state.get('current_node', 'unknown')}")
            logger.info(f"引用ID: {reference_id}, 类型: {reference_type}")
#             logger.debug(f"输入状态: {_truncate_for_logging(input_state)}")
            
            # 调用原始函数
            try:
                # 对于CompiledStateGraph类型，使用invoke方法而不是直接调用
                result = original_agent.invoke(state)
                
                # 计算持续时间
                end_time = time.time()
                duration_ms = int((end_time - start_time) * 1000)
                end_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time))
                
                # 提取LLM调用信息（如果可能）
                model_name = "unknown"
                if hasattr(original_agent, "model") and hasattr(original_agent.model, "model_name"):
                    model_name = original_agent.model.model_name
                
                # 记录调用结束详细日志
                logger.info(f"====== 结束调用智能体 {agent_name} ======")
                logger.info(f"完成时间: {end_timestamp}")
                logger.info(f"耗时: {duration_ms}ms")
                logger.info(f"使用模型: {model_name}")
                logger.debug(f"智能体返回结果: {_truncate_for_logging(result)}")
                
                # 保存成功调用记录
                if db_service:
                    db_service.save_llm_call(
                        agent_name=agent_name,
                        node_name=state.get("current_node", "unknown"),
                        input_data=input_state,
                        output_data=result,
                        status="SUCCESS",
                        reference_id=reference_id,
                        reference_type=reference_type,
                        duration_ms=duration_ms,
                        model_name=model_name
                    )
                    
                return result
                
            except Exception as e:
                # 计算持续时间
                end_time = time.time()
                duration_ms = int((end_time - start_time) * 1000)
                end_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time))
                
                # 记录调用失败详细日志
                logger.error(f"====== 智能体 {agent_name} 调用失败 ======")
                logger.error(f"失败时间: {end_timestamp}")
                logger.error(f"耗时: {duration_ms}ms")
                logger.error(f"错误信息: {str(e)}")
                
                # 保存失败调用记录
                if db_service:
                    db_service.save_llm_call(
                        agent_name=agent_name,
                        node_name=state.get("current_node", "unknown"),
                        input_data=state,
                        output_data=None,
                        status="FAILED",
                        reference_id=reference_id,
                        reference_type=reference_type,
                        duration_ms=duration_ms,
                        error_message=str(e),
                        model_name="unknown"
                    )
                
                # 重新抛出异常
                raise
                
        return wrapper
    else:
        # 原始的装饰器实现，用于处理普通可调用对象
        @functools.wraps(original_agent)
        def wrapper(state: Dict[str, Any], *args, **kwargs):
            global db_service
            if db_service is None:
                # 如果数据库服务未初始化，尝试初始化
                from src.config import get_db_config
                setup_db_service(get_db_config())
                
            # 获取参考ID（如果在state中有）
            reference_id = None
            reference_type = None
            
            if 'objective_id' in state:
                reference_id = state['objective_id']
                reference_type = 'OBJECTIVE'
            elif 'current_task' in state and 'id' in state['current_task']:
                reference_id = state['current_task']['id']
                reference_type = 'TASK'
            elif 'task_id' in state:
                reference_id = state['task_id']
                reference_type = 'TASK'
                
            # 记录开始时间
            start_time = time.time()
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))
            
            # 复制输入状态作为记录
            input_state = {k: v for k, v in state.items() if not k.startswith('_')}
            
            # 记录调用开始详细日志
            logger.info(f"====== 开始调用智能体 {agent_name} [直接调用] ======")
            logger.info(f"调用时间: {timestamp}")
            logger.info(f"节点名称: {state.get('current_node', 'unknown')}")
            logger.info(f"引用ID: {reference_id}, 类型: {reference_type}")
#             logger.debug(f"输入状态: {_truncate_for_logging(input_state)}")
            
            # 调用原始函数
            try:
                # 调用原始智能体
                result = original_agent(state, *args, **kwargs)
                
                # 计算持续时间
                end_time = time.time()
                duration_ms = int((end_time - start_time) * 1000)
                end_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time))
                
                # 提取LLM调用信息（如果可能）
                model_name = "unknown"
                if hasattr(original_agent, "model") and hasattr(original_agent.model, "model_name"):
                    model_name = original_agent.model.model_name
                
                # 记录调用结束详细日志
                logger.info(f"====== 结束调用智能体 {agent_name} ======")
                logger.info(f"完成时间: {end_timestamp}")
                logger.info(f"耗时: {duration_ms}ms")
                logger.info(f"使用模型: {model_name}")
                logger.debug(f"智能体返回结果: {_truncate_for_logging(result)}")
                
                # 保存成功调用记录
                if db_service:
                    db_service.save_llm_call(
                        agent_name=agent_name,
                        node_name=state.get("current_node", "unknown"),
                        input_data=input_state,
                        output_data=result,
                        status="SUCCESS",
                        reference_id=reference_id,
                        reference_type=reference_type,
                        duration_ms=duration_ms,
                        model_name=model_name
                    )
                    
                return result
                
            except Exception as e:
                # 计算持续时间
                end_time = time.time()
                duration_ms = int((end_time - start_time) * 1000)
                end_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time))
                
                # 记录调用失败详细日志
                logger.error(f"====== 智能体 {agent_name} 调用失败 ======")
                logger.error(f"失败时间: {end_timestamp}")
                logger.error(f"耗时: {duration_ms}ms")
                logger.error(f"错误信息: {str(e)}")
                
                # 保存失败调用记录
                if db_service:
                    db_service.save_llm_call(
                        agent_name=agent_name,
                        node_name=state.get("current_node", "unknown"),
                        input_data=state,
                        output_data=None,
                        status="FAILED",
                        reference_id=reference_id,
                        reference_type=reference_type,
                        duration_ms=duration_ms,
                        error_message=str(e),
                        model_name="unknown"
                    )
                
                # 重新抛出异常
                raise
                
        return wrapper

def wrap_create_agent(create_agent_func):
    """装饰create_agent工厂函数，对所有创建的智能体应用log_llm_call装饰器"""
    @functools.wraps(create_agent_func)
    def wrapper(agent_name, agent_type, tools, prompt_template, *args, **kwargs):
        # 创建原始智能体
        original_agent = create_agent_func(agent_name, agent_type, tools, prompt_template, *args, **kwargs)
        
        # 应用LLM调用日志装饰器
        wrapped_agent = log_llm_call(original_agent)
        
        # 复制原始智能体的属性到包装后的智能体
        for attr_name in dir(original_agent):
            if not attr_name.startswith('__'):
                try:
                    setattr(wrapped_agent, attr_name, getattr(original_agent, attr_name))
                except (AttributeError, TypeError):
                    pass
        
        # 添加原始名称
        setattr(wrapped_agent, "name", agent_name)
        
        # 记录包装后的智能体类型
        logger.debug(f"智能体 {agent_name} 包装后的类型: {type(wrapped_agent).__name__}")
        
        return wrapped_agent
    return wrapper 