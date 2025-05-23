import uuid
import json
import logging
import pymysql
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple

# 添加新的导入
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

class MySQLService:
    """MySQL数据库服务类"""
    
    def __init__(self, config: Dict):
        """初始化数据库连接"""
        self.config = config
        self.connection = None
        self.logger = logging.getLogger(__name__)
        
    def connect(self):
        """建立数据库连接"""
        if self.connection is None:
            try:
#                 self.logger.info(f"正在连接数据库，配置信息: {self.config}")
                self.connection = pymysql.connect(
                    host=self.config.get("host", "localhost"),
                    user=self.config.get("user", "root"),
                    password=self.config.get("password", ""),
                    database=self.config.get("database", "deerflow"),
                    charset="utf8mb4",
                    cursorclass=pymysql.cursors.DictCursor
                )
#                 self.logger.info("数据库连接成功")
            except Exception as e:
                self.logger.error(f"数据库连接失败: {str(e)}")
                raise e
            
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
            
    def execute_query(self, sql: str, params: tuple = None) -> List[Dict]:
        """执行查询并返回结果"""
        self.connect()
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        finally:
            self.connection.commit()
            
    def execute_insert(self, table: str, data: Dict) -> str:
        """插入数据并返回ID"""
        self.connect()
        
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        values = tuple(data.values())
        
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, values)
                self.connection.commit()
                return data.get('call_id', cursor.lastrowid)
        except Exception as e:
            self.connection.rollback()
            raise e
            
    def save_llm_call(self, agent_name: str, node_name: str, input_data: Any, 
                     output_data: Any, status: str = "SUCCESS", 
                     reference_id: Optional[str] = None, 
                     reference_type: Optional[str] = None,
                     tokens_used: Optional[int] = None,
                     duration_ms: Optional[int] = None,
                     error_message: Optional[str] = None,
                     model_name: Optional[str] = None,
                     metadata: Optional[Dict] = None) -> str:
        """保存LLM调用记录"""
        # 准备数据
        call_data = {
            'call_id': str(uuid.uuid4()),
            'agent_name': agent_name,
            'node_name': node_name,
            'reference_id': reference_id,
            'reference_type': reference_type,
            'input_data': self._serialize_for_database(input_data),
            'output_data': self._serialize_for_database(output_data),
            'tokens_used': tokens_used,
            'duration_ms': duration_ms,
            'status': status,
            'error_message': error_message,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'model_name': model_name,
            'metadata': self._serialize_for_database(metadata) if metadata else None
        }
        
        return self.execute_insert('agent_llm_calls', call_data)
        
    def save_objective_decomposer_result(self, llm_response: Union[str, Dict],msg_id:str) -> List[str]:
        """保存目标分解智能体的结果到objectives表
        
        Args:
            llm_response: 智能体返回的JSON字符串或字典
            
        Returns:
            objective_ids: 保存的目标ID列表
        """
        # 如果输入是字符串，尝试解析为JSON
        if isinstance(llm_response, str):
            try:
                objectives = json.loads(llm_response)
            except json.JSONDecodeError:
                # 如果不是有效的JSON，尝试使用正则表达式提取
                objectives = self._extract_objectives_from_text(llm_response)
        else:
            objectives = llm_response
        
        # 确保objectives是一个列表
        if not isinstance(objectives, list):
            if "objectives" in objectives:
                objectives = objectives["objectives"]
            else:
                objectives = [objectives]
        
        objective_ids = []
        
        # 获取数据库连接
        self.connect()
        
        try:
            for objective in objectives:
                objective_id =  msg_id+'_'+objective.get("objective_id", str(uuid.uuid4()))
                
                # 准备数据
                current_time =datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                data = {
                    'msg_id': msg_id,
                    'objective_id': objective_id,
                    'title': objective.get("title", ""),
                    'description': objective.get("description", ""),
                    'justification': objective.get("justification", ""),
                    'evaluation_criteria': objective.get("evaluation_criteria", ""),
                    'status': objective.get("status", "CREATED"),
                    'created_at': current_time,
                    'updated_at': current_time,
                    'retry_count': objective.get("retry_count", 0),
                    'max_retries': objective.get("max_retries", 3)
                }
                
                # 执行插入
                self.execute_insert('objectives', data)
                objective_ids.append(objective_id)
        except Exception as e:
            self.logger.error(f"保存处理结果失败: {str(e)}")
            # 错误时回滚
            if self.connection:
                self.connection.rollback()
            raise e
        
        return objective_ids
        
    def _extract_objectives_from_text(self, text: str) -> List[Dict]:
        """从文本中提取目标信息
        
        Args:
            text: 文本内容
            
        Returns:
            objectives: 提取的目标列表
        """
        # 简单实现，实际使用可能需要更复杂的逻辑
        import re
        objectives = []
        
        # 尝试提取目标模式
        objective_pattern = r'title["\']?\s*:\s*["\']([^"\']+)["\']'
        titles = re.findall(objective_pattern, text)
        
        desc_pattern = r'description["\']?\s*:\s*["\']([^"\']+)["\']'
        descriptions = re.findall(desc_pattern, text)
        
        # 将提取的标题和描述组合成目标
        for i in range(len(titles)):
            objective = {
                "title": titles[i],
                "description": descriptions[i] if i < len(descriptions) else ""
            }
            objectives.append(objective)
        
        return objectives
        
    def save_task_analyzer_result(self, objective_id: str,msg_id:str, tasks: []) -> Dict[str, List[str]]:
        """保存任务分析智能体的结果到tasks和steps表
        
        Args:
            objective_id: 关联的目标ID
            tasks: 智能体返回的数组
            
        Returns:
            ids: 包含task_ids和step_ids的字典
        """

        # 提取任务和步骤
        task_ids = []
        step_ids = []
        
        # 获取数据库连接
        self.connect()
        
        try:
            for task in tasks:
                task_id = task.get("task_id", str(uuid.uuid4()))
                
                # 准备任务数据
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                task_data = {
                    'msg_id': msg_id,
                    'task_id': task_id,
                    'objective_id': objective_id,
                    'title': task.get("title", ""),
                    'description': task.get("description", ""),
                    'status': task.get("status", "PENDING"),
                    'priority': task.get("priority", 0),
                    'created_at': current_time,
                    'updated_at': current_time,
                    'is_sufficient': task.get("is_sufficient", False),
                    'evaluation_criteria': task.get("evaluation_criteria", ""),
                    'retry_count': task.get("retry_count", 0),
                    'max_retries': task.get("max_retries", 3)
                }
                
                # 执行任务插入
                self.execute_insert('tasks', task_data)
                task_ids.append(task_id)
                
                # 处理任务的步骤
                steps = task.get("steps", [])
                for step in steps:
                    step_id = step.get("step_id", str(uuid.uuid4()))
                    
                    # 准备步骤数据
                    step_data = {
                        'step_id': step_id,
                        'task_id': task_id,
                        'title': step.get("title", ""),
                        'description': step.get("description", ""),
                        'status': step.get("status", "PENDING"),
                        'priority': step.get("priority", 0),
                        'created_at': current_time,
                        'updated_at': current_time,
                        'is_sufficient': step.get("is_sufficient", False),
                        'evaluation_criteria': step.get("evaluation_criteria", ""),
                        'retry_count': step.get("retry_count", 0),
                        'max_retries': step.get("max_retries", 3),
                        'timeout_seconds': step.get("timeout_seconds", 300)
                    }
                    
                    # 执行步骤插入
                    self.execute_insert('steps', step_data)
                    step_ids.append(step_id)
            
        except Exception as e:
            # 错误时回滚
            if self.connection:
                self.connection.rollback()
            raise e
        
        return {"task_ids": task_ids, "step_ids": step_ids}
        
    def _extract_tasks_from_text(self, text: str) -> Dict:
        """从文本中提取任务信息
        
        Args:
            text: 文本内容
            
        Returns:
            tasks: 提取的任务字典
        """
        # 实际使用可能需要更复杂的逻辑
        import re
        tasks = []
        
        # 尝试提取任务模式
        task_pattern = r'title["\']?\s*:\s*["\']([^"\']+)["\']'
        titles = re.findall(task_pattern, text)
        
        desc_pattern = r'description["\']?\s*:\s*["\']([^"\']+)["\']'
        descriptions = re.findall(desc_pattern, text)
        
        # 将提取的标题和描述组合成任务
        for i in range(len(titles)):
            task = {
                "title": titles[i],
                "description": descriptions[i] if i < len(descriptions) else "",
                "steps": []
            }
            tasks.append(task)
        
        return {"tasks": tasks}
        
    def save_agent_content(self, reference_id: str, reference_type: str, 
                          content: str, content_type: str, metadata: Optional[Dict] = None) -> str:
        """保存智能体生成的内容到contents表
        
        Args:
            reference_id: 关联的任务或步骤ID
            reference_type: 引用类型，'TASK'或'STEP'
            content: 内容文本
            content_type: 内容类型，如'DIFY_KNOWLEDGE', 'CRAWLED_DATA', 'AGENT_RESULT'
            metadata: 元数据字典
            
        Returns:
            content_id: 保存的内容ID
        """
        content_id = str(uuid.uuid4())
        
        # 获取数据库连接
        self.connect()
        
        try:
            # 准备数据
            metadata_json = json.dumps(metadata) if metadata else None
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            data = {
                'content_id': content_id,
                'reference_id': reference_id,
                'reference_type': reference_type,
                'content_type': content_type,
                'content': content,
                'metadata': metadata_json,
                'created_at': current_time
            }
            
            # 执行插入
            self.execute_insert('contents', data)
            
        except Exception as e:
            # 错误时回滚
            if self.connection:
                self.connection.rollback()
            raise e
        
        return content_id
        
    def update_step_status(self, step_id: str, status: str, is_sufficient: bool = None) -> bool:
        """更新步骤状态
        
        Args:
            step_id: 步骤ID
            status: 新状态
            is_sufficient: 是否充分
            
        Returns:
            success: 更新是否成功
        """
        # 获取数据库连接
        self.connect()
        
        try:
            # 准备更新数据
            data = {'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            # 添加状态
            data['status'] = status
            
            # 如果提供了是否充分，添加到更新数据中
            if is_sufficient is not None:
                data['is_sufficient'] = is_sufficient
                
            # 如果状态是COMPLETED，添加完成时间
            if status == 'COMPLETED':
                data['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
            # 构建更新SQL
            columns = []
            values = []
            
            for key, value in data.items():
                columns.append(f"{key} = %s")
                values.append(value)
                
            # 添加WHERE条件
            values.append(step_id)
            
            sql = f"UPDATE steps SET {', '.join(columns)} WHERE step_id = %s"
            
            # 执行更新
            with self.connection.cursor() as cursor:
                affected_rows = cursor.execute(sql, tuple(values))
                self.connection.commit()
                return affected_rows > 0
            
        except Exception as e:
            # 错误时回滚
            if self.connection:
                self.connection.rollback()
            raise e
            
    def update_task_status(self, task_id: str, status: str, is_sufficient: bool = None) -> bool:
        """更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            is_sufficient: 是否充分
            
        Returns:
            success: 更新是否成功
        """
        # 获取数据库连接
        self.connect()
        
        try:
            # 准备更新数据
            data = {'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            # 添加状态
            data['status'] = status
            
            # 如果提供了是否充分，添加到更新数据中
            if is_sufficient is not None:
                data['is_sufficient'] = is_sufficient
                
            # 如果状态是COMPLETED，添加完成时间
            if status == 'COMPLETED':
                data['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
            # 构建更新SQL
            columns = []
            values = []
            
            for key, value in data.items():
                columns.append(f"{key} = %s")
                values.append(value)
                
            # 添加WHERE条件
            values.append(task_id)
            
            sql = f"UPDATE tasks SET {', '.join(columns)} WHERE task_id = %s"
            
            # 执行更新
            with self.connection.cursor() as cursor:
                affected_rows = cursor.execute(sql, tuple(values))
                self.connection.commit()
                return affected_rows > 0
            
        except Exception as e:
            # 错误时回滚
            if self.connection:
                self.connection.rollback()
            raise e
            
    def update_objective_status(self, objective_id: str, status: str, completed_at: datetime = None) -> bool:
        """更新目标状态
        
        Args:
            objective_id: 目标ID
            status: 新状态
            completed_at: 完成时间
            
        Returns:
            success: 更新是否成功
        """
        # 获取数据库连接
        self.connect()
        
        try:
            # 准备更新数据
            data = {'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            # 添加状态
            data['status'] = status
            
            # 如果提供了完成时间，添加到更新数据中
            if completed_at:
                if isinstance(completed_at, datetime):
                    data['completed_at'] = completed_at.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    data['completed_at'] = completed_at
            elif status == 'COMPLETED':
                # 如果状态是COMPLETED但没有提供完成时间，使用当前时间
                data['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
            # 构建更新SQL
            columns = []
            values = []
            
            for key, value in data.items():
                columns.append(f"{key} = %s")
                values.append(value)
                
            # 添加WHERE条件
            values.append(objective_id)
            
            sql = f"UPDATE objectives SET {', '.join(columns)} WHERE objective_id = %s"
            
            # 执行更新
            with self.connection.cursor() as cursor:
                affected_rows = cursor.execute(sql, tuple(values))
                self.connection.commit()
                return affected_rows > 0
            
        except Exception as e:
            # 错误时回滚
            if self.connection:
                self.connection.rollback()
            raise e
            
    def save_context_analysis_result(self, msg_id: str, llm_response: Union[str, Dict]) -> str:
        """保存上下文分析智能体的结果到business_analyses表
        
        Args:
            objective_id: 关联的目标ID
            llm_response: 智能体返回的JSON字符串或字典
            
        Returns:
            analysis_id: 保存的分析ID
        """
        # 获取数据库连接
        self.connect()
        
        try:
            # 处理数组字段
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 提取content内容
            content_json = None
            if isinstance(llm_response, dict) and "messages" in llm_response:
                messages = json.loads(llm_response["messages"])
                for message in messages:
                    message_obj = json.loads(message)
                    if message_obj.get("type") == "AIMessage" and "content" in message_obj:
                        content_json = message_obj["content"]
                        break
            
            data = {
                'msg_id': msg_id,
                'content': content_json,  # 新增：保存content内容
                'llm_response': json.dumps(llm_response),  # 新增：保存原始响应
                'created_at': current_time,
            }
            
            # 执行插入
            self.execute_insert('context_analysis', data)
            
        except Exception as e:
            # 错误时回滚
            if self.connection:
                self.connection.rollback()
            raise e
        
        return msg_id

    def save_research_result(self, task_id: str, llm_response: Union[str, Dict]) -> str:
        """保存研究智能体的结果到research_results表
        
        Args:
            task_id: 关联的任务ID
            llm_response: 智能体返回的JSON字符串或字典
            
        Returns:
            result_id: 保存的研究结果ID
        """
        # 如果输入是字符串，尝试解析为JSON
        if isinstance(llm_response, str):
            try:
                research_data = json.loads(llm_response)
            except json.JSONDecodeError:
                # 如果不是有效的JSON，直接使用文本
                research_data = {"text_content": llm_response}
        else:
            research_data = llm_response
        
        result_id = str(uuid.uuid4())
        
        # 获取数据库连接
        self.connect()
        
        try:
            # 准备数据
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 序列化研究结果
            serialized_result = self._serialize_for_database(research_data)
            
            data = {
                'result_id': result_id,
                'task_id': task_id,
                'research_data': serialized_result,
                'created_at': current_time,
                'updated_at': current_time,
                'status': 'COMPLETED'
            }
            
            # 执行插入
            self.execute_insert('research_results', data)
            
        except Exception as e:
            # 错误时回滚
            if self.connection:
                self.connection.rollback()
            self.logger.error(f"保存研究结果失败: {str(e)}")
            raise e
        
        return result_id
    
    def save_processing_result(self, category: str, llm_response: Union[str, Dict]) -> str:
        """保存处理智能体的结果到processing_results表
        
        Args:
            category: 处理结果的类别
            llm_response: 智能体返回的JSON字符串或字典
            
        Returns:
            process_id: 保存的处理结果ID
        """
        # 如果输入是字符串，尝试解析为JSON
        if isinstance(llm_response, str):
            try:
                processing_data = json.loads(llm_response)
            except json.JSONDecodeError:
                # 如果不是有效的JSON，直接使用文本
                processing_data = {"text_content": llm_response}
        else:
            processing_data = llm_response
        
        process_id = str(uuid.uuid4())
        
        # 获取数据库连接
        self.connect()
        
        try:
            # 准备数据
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 序列化处理结果
            serialized_result = self._serialize_for_database(processing_data)
            
            data = {
                'process_id': process_id,
                'category': category,
                'processing_data': serialized_result,
                'created_at': current_time,
                'updated_at': current_time,
                'status': 'COMPLETED'
            }
            
            # 执行插入
            self.execute_insert('processing_results', data)
            
        except Exception as e:
            # 错误时回滚
            if self.connection:
                self.connection.rollback()
            self.logger.error(f"保存处理结果失败: {str(e)}")
            raise e
        
        return process_id
    
    def save_quality_evaluation_result(self, task_id: str, llm_response: Union[str, Dict], quality_passed: bool = False) -> str:
        """保存质量评估智能体的结果到quality_evaluations表
        
        Args:
            task_id: 关联的任务ID
            llm_response: 智能体返回的JSON字符串或字典
            quality_passed: 质量评估是否通过
            
        Returns:
            evaluation_id: 保存的评估结果ID
        """
        # 如果输入是字符串，尝试解析为JSON
        if isinstance(llm_response, str):
            try:
                evaluation_data = json.loads(llm_response)
            except json.JSONDecodeError:
                # 如果不是有效的JSON，直接使用文本
                evaluation_data = {"text_content": llm_response}
        else:
            evaluation_data = llm_response
        
        evaluation_id = str(uuid.uuid4())
        
        # 获取数据库连接
        self.connect()
        
        try:
            # 准备数据
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 序列化评估结果
            serialized_result = self._serialize_for_database(evaluation_data)
            
            data = {
                'evaluation_id': evaluation_id,
                'task_id': task_id,
                'evaluation_data': serialized_result,
                'quality_passed': quality_passed,
                'created_at': current_time,
                'updated_at': current_time
            }
            
            # 执行插入
            self.execute_insert('quality_evaluations', data)
            
        except Exception as e:
            # 错误时回滚
            if self.connection:
                self.connection.rollback()
            self.logger.error(f"保存质量评估结果失败: {str(e)}")
            raise e
        
        return evaluation_id
    
    def save_synthesis_result(self, llm_response: Union[str, Dict]) -> str:
        """保存合成智能体的结果到synthesis_results表
        
        Args:
            llm_response: 智能体返回的JSON字符串或字典
            
        Returns:
            synthesis_id: 保存的合成结果ID
        """
        # 如果输入是字符串，尝试解析为JSON
        if isinstance(llm_response, str):
            try:
                synthesis_data = json.loads(llm_response)
            except json.JSONDecodeError:
                # 如果不是有效的JSON，直接使用文本
                synthesis_data = {"text_content": llm_response}
        else:
            synthesis_data = llm_response
        
        synthesis_id = str(uuid.uuid4())
        
        # 获取数据库连接
        self.connect()
        
        try:
            # 准备数据
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 序列化合成结果
            serialized_result = self._serialize_for_database(synthesis_data)
            
            data = {
                'synthesis_id': synthesis_id,
                'synthesis_data': serialized_result,
                'created_at': current_time,
                'updated_at': current_time,
                'status': 'COMPLETED'
            }
            
            # 执行插入
            self.execute_insert('synthesis_results', data)
            
        except Exception as e:
            # 错误时回滚
            if self.connection:
                self.connection.rollback()
            self.logger.error(f"保存合成结果失败: {str(e)}")
            raise e
        
        return synthesis_id
    
    def save_error_log(self, error_type: str, error_message: str, error_source: str, traceback: str = "") -> str:
        """保存错误日志到error_logs表
        
        Args:
            error_type: 错误类型
            error_message: 错误消息
            error_source: 错误来源
            traceback: 错误堆栈跟踪
            
        Returns:
            log_id: 保存的日志ID
        """
        log_id = str(uuid.uuid4())
        
        # 获取数据库连接
        self.connect()
        
        try:
            # 准备数据
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            data = {
                'log_id': log_id,
                'error_type': error_type,
                'error_message': error_message,
                'error_source': error_source,
                'traceback': traceback,
                'created_at': current_time
            }
            
            # 执行插入
            self.execute_insert('error_logs', data)
            
        except Exception as e:
            # 错误时回滚
            if self.connection:
                self.connection.rollback()
            self.logger.error(f"保存错误日志失败: {str(e)}")
            raise e
        
        return log_id
    
    def _serialize_for_database(self, obj):
        """将对象序列化为可保存到数据库的格式
        
        Args:
            obj: 需要序列化的对象
            
        Returns:
            序列化后的对象
        """
        if isinstance(obj, (dict, list)):
            try:
                # 尝试使用标准json序列化
                return json.dumps(obj, ensure_ascii=False)
            except TypeError:
                # 如果标准序列化失败，使用自定义处理
                if isinstance(obj, dict):
                    return json.dumps({k: self._serialize_for_database(v) for k, v in obj.items()}, ensure_ascii=False)
                elif isinstance(obj, list):
                    return json.dumps([self._serialize_for_database(item) for item in obj], ensure_ascii=False)
        elif isinstance(obj, (HumanMessage, AIMessage, SystemMessage, BaseMessage)):
            # 处理LangChain消息类型
            message_dict = {
                "type": obj.__class__.__name__,
                "content": obj.content
            }
            if hasattr(obj, "additional_kwargs") and obj.additional_kwargs:
                message_dict["additional_kwargs"] = obj.additional_kwargs
            return json.dumps(message_dict, ensure_ascii=False)
        elif hasattr(obj, "to_json"):
            # 处理有to_json方法的对象
            return obj.to_json()
        elif hasattr(obj, "__dict__"):
            # 处理一般Python对象
            return json.dumps(obj.__dict__, ensure_ascii=False)
        else:
            # 最后的备选方案，简单地转换为字符串
            return str(obj)