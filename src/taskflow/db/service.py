# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow数据库服务模块。

提供数据库操作的服务函数，包括初始化和CRUD操作。
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Union, Tuple

from sqlalchemy import and_, or_, desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from src.taskflow.db.base import Base, engine, SessionLocal, db_session
from src.taskflow.db.models import Objective, Task, Step, Workflow, WorkflowCheckpoint, IndustryStandard
from src.taskflow.exceptions import (
    DatabaseError, ObjectiveNotFoundError, TaskNotFoundError, 
    StepNotFoundError, WorkflowNotFoundError
)

# 类型变量，用于泛型
T = TypeVar("T", bound=Base)

# 获取日志记录器
logger = logging.getLogger(__name__)


def init_database() -> None:
    """
    初始化数据库，创建所有表。
    
    如果表已存在，不会重新创建。
    """
    try:
        # 导入所有模型以确保它们已注册
        from src.taskflow.db import models
        
        # 创建表
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表已成功初始化")
    except SQLAlchemyError as e:
        logger.error(f"初始化数据库时出错: {str(e)}")
        raise DatabaseError(f"无法初始化数据库: {str(e)}")


class CRUDBase(Generic[T]):
    """
    提供基本CRUD操作的基类。
    
    泛型参数T应该是SQLAlchemy模型类。
    """
    
    def __init__(self, model: Type[T]):
        """
        初始化CRUD服务。
        
        Args:
            model: 数据模型类
        """
        self.model = model
    
    def get(self, db: Session, id: str) -> Optional[T]:
        """
        通过ID获取单个对象。
        
        Args:
            db: 数据库会话
            id: 对象ID
            
        Returns:
            找到的对象或None
        """
        return db.query(self.model).filter(self.model.id == id).first()
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[T]:
        """
        获取多个对象。
        
        Args:
            db: 数据库会话
            skip: 跳过的记录数
            limit: 返回的最大记录数
            filters: 过滤条件字典
            
        Returns:
            对象列表
        """
        query = db.query(self.model)
        
        # 应用过滤条件
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.filter(getattr(self.model, field) == value)
        
        return query.offset(skip).limit(limit).all()
    
    def create(self, db: Session, *, obj_in: Dict[str, Any]) -> T:
        """
        创建新对象。
        
        Args:
            db: 数据库会话
            obj_in: 输入数据字典
            
        Returns:
            创建的对象
        """
        try:
            db_obj = self.model(**obj_in)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"创建{self.model.__name__}时出错: {str(e)}")
            raise DatabaseError(f"无法创建{self.model.__name__}: {str(e)}")
    
    def update(
        self, 
        db: Session, 
        *, 
        db_obj: T, 
        obj_in: Union[Dict[str, Any], Any]
    ) -> T:
        """
        更新对象。
        
        Args:
            db: 数据库会话
            db_obj: 数据库中的现有对象
            obj_in: 更新数据（字典或Pydantic模型）
            
        Returns:
            更新后的对象
        """
        try:
            # 如果是字典，直接使用
            if isinstance(obj_in, dict):
                update_data = obj_in
            else:
                # 否则，转换为字典
                update_data = obj_in.dict(exclude_unset=True)
            
            # 更新属性
            for field in update_data:
                if hasattr(db_obj, field):
                    setattr(db_obj, field, update_data[field])
            
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"更新{self.model.__name__}时出错: {str(e)}")
            raise DatabaseError(f"无法更新{self.model.__name__}: {str(e)}")
    
    def delete(self, db: Session, *, id: str) -> Optional[T]:
        """
        删除对象。
        
        Args:
            db: 数据库会话
            id: 对象ID
            
        Returns:
            删除的对象或None
        """
        try:
            obj = db.query(self.model).get(id)
            if obj:
                db.delete(obj)
                db.commit()
            return obj
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"删除{self.model.__name__}时出错: {str(e)}")
            raise DatabaseError(f"无法删除{self.model.__name__}: {str(e)}")


class ObjectiveService(CRUDBase[Objective]):
    """目标对象服务类，提供特定于目标的数据库操作"""
    
    def get_with_tasks(self, db: Session, objective_id: str) -> Optional[Objective]:
        """
        获取目标及其所有任务。
        
        Args:
            db: 数据库会话
            objective_id: 目标ID
            
        Returns:
            找到的目标(包含任务)或None
            
        Raises:
            ObjectiveNotFoundError: 目标不存在时
        """
        objective = db.query(Objective).options(
            joinedload(Objective.tasks)
        ).filter(Objective.id == objective_id).first()
        
        if not objective:
            raise ObjectiveNotFoundError(f"目标ID不存在: {objective_id}")
        
        return objective
    
    def update_status(self, db: Session, objective_id: str, status: str) -> Objective:
        """
        更新目标状态。
        
        Args:
            db: 数据库会话
            objective_id: 目标ID
            status: 新状态
            
        Returns:
            更新后的目标
            
        Raises:
            ObjectiveNotFoundError: 目标不存在时
        """
        objective = self.get(db, objective_id)
        if not objective:
            raise ObjectiveNotFoundError(f"目标ID不存在: {objective_id}")
        
        update_data = {"status": status, "updated_at": datetime.now()}
        if status == "COMPLETED":
            update_data["completed_at"] = datetime.now()
        
        return self.update(db, db_obj=objective, obj_in=update_data)
    
    def get_by_user(
        self, 
        db: Session, 
        user_id: str, 
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
    ) -> List[Objective]:
        """
        获取用户的所有目标。
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            status: 可选的状态过滤
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            目标列表
        """
        query = db.query(Objective).filter(Objective.user_id == user_id)
        
        if status:
            query = query.filter(Objective.status == status)
        
        return query.order_by(desc(Objective.created_at)).offset(skip).limit(limit).all()
    
    def get_objectives_with_stats(
        self, 
        db: Session, 
        filters: Optional[Dict[str, Any]] = None,
        skip: int = 0,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取目标列表，包含任务统计信息。
        
        Args:
            db: 数据库会话
            filters: 过滤条件
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            带有统计信息的目标列表
        """
        query = db.query(Objective)
        
        # 应用过滤条件
        if filters:
            for field, value in filters.items():
                if hasattr(Objective, field):
                    query = query.filter(getattr(Objective, field) == value)
        
        objectives = query.order_by(desc(Objective.created_at)).offset(skip).limit(limit).all()
        
        # 添加统计信息
        result = []
        for obj in objectives:
            # 获取任务计数
            task_count = db.query(Task).filter(Task.objective_id == obj.id).count()
            # 获取已完成任务计数
            completed_task_count = db.query(Task).filter(
                Task.objective_id == obj.id,
                Task.status == "COMPLETED"
            ).count()
            
            # 计算完成百分比
            completion_percentage = 0
            if task_count > 0:
                completion_percentage = int((completed_task_count / task_count) * 100)
            
            # 组装结果
            obj_dict = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
            obj_dict.update({
                "task_count": task_count,
                "completed_task_count": completed_task_count,
                "completion_percentage": completion_percentage
            })
            result.append(obj_dict)
        
        return result


class TaskService(CRUDBase[Task]):
    """任务服务类，提供特定于任务的数据库操作"""
    
    def get_with_steps(self, db: Session, task_id: str) -> Optional[Task]:
        """
        获取任务及其所有步骤。
        
        Args:
            db: 数据库会话
            task_id: 任务ID
            
        Returns:
            找到的任务(包含步骤)或None
            
        Raises:
            TaskNotFoundError: 任务不存在时
        """
        task = db.query(Task).options(
            joinedload(Task.steps)
        ).filter(Task.id == task_id).first()
        
        if not task:
            raise TaskNotFoundError(f"任务ID不存在: {task_id}")
        
        return task
    
    def update_status(self, db: Session, task_id: str, status: str) -> Task:
        """
        更新任务状态。
        
        Args:
            db: 数据库会话
            task_id: 任务ID
            status: 新状态
            
        Returns:
            更新后的任务
            
        Raises:
            TaskNotFoundError: 任务不存在时
        """
        task = self.get(db, task_id)
        if not task:
            raise TaskNotFoundError(f"任务ID不存在: {task_id}")
        
        update_data = {"status": status, "updated_at": datetime.now()}
        if status == "COMPLETED":
            update_data["completed_at"] = datetime.now()
            
            # 检查所有步骤是否已完成
            incomplete_steps = db.query(Step).filter(
                Step.task_id == task_id,
                Step.status != "COMPLETED"
            ).count()
            
            if incomplete_steps > 0:
                logger.warning(f"将任务 {task_id} 标记为完成，但还有 {incomplete_steps} 个未完成的步骤")
        
        return self.update(db, db_obj=task, obj_in=update_data)
    
    def get_by_objective(
        self, 
        db: Session, 
        objective_id: str,
        status: Optional[str] = None,
        task_type: Optional[str] = None
    ) -> List[Task]:
        """
        获取目标下的所有任务。
        
        Args:
            db: 数据库会话
            objective_id: 目标ID
            status: 可选的状态过滤
            task_type: 可选的任务类型过滤
            
        Returns:
            任务列表
        """
        query = db.query(Task).filter(Task.objective_id == objective_id)
        
        if status:
            query = query.filter(Task.status == status)
        
        if task_type:
            query = query.filter(Task.task_type == task_type)
        
        return query.order_by(Task.priority.desc(), Task.created_at).all()
    
    def get_task_dependencies(self, db: Session, task_id: str) -> Tuple[List[Task], List[Task]]:
        """
        获取任务的依赖任务和被依赖任务。
        
        Args:
            db: 数据库会话
            task_id: 任务ID
            
        Returns:
            依赖任务列表和被依赖任务列表的元组
            
        Raises:
            TaskNotFoundError: 任务不存在时
        """
        task = self.get(db, task_id)
        if not task:
            raise TaskNotFoundError(f"任务ID不存在: {task_id}")
        
        # 获取当前任务依赖的任务
        depends_on_tasks = []
        if task.depends_on:
            depends_on_ids = task.depends_on
            depends_on_tasks = db.query(Task).filter(Task.id.in_(depends_on_ids)).all()
        
        # 获取依赖当前任务的任务
        dependents = db.query(Task).filter(
            Task.depends_on.isnot(None)
        ).all()
        
        dependent_tasks = []
        for dependent in dependents:
            if dependent.depends_on and task_id in dependent.depends_on:
                dependent_tasks.append(dependent)
        
        return (depends_on_tasks, dependent_tasks)
    
    def check_dependency_status(self, db: Session, task_id: str) -> Dict[str, Any]:
        """
        检查任务依赖的状态。
        
        Args:
            db: 数据库会话
            task_id: 任务ID
            
        Returns:
            依赖状态信息
            
        Raises:
            TaskNotFoundError: 任务不存在时
        """
        task = self.get(db, task_id)
        if not task:
            raise TaskNotFoundError(f"任务ID不存在: {task_id}")
        
        result = {
            "ready_to_execute": True,
            "pending_dependencies": [],
            "completed_dependencies": []
        }
        
        # 检查依赖
        if task.depends_on:
            for dep_id in task.depends_on:
                dep_task = self.get(db, dep_id)
                if not dep_task:
                    logger.warning(f"任务 {task_id} 依赖的任务 {dep_id} 不存在")
                    result["pending_dependencies"].append({
                        "id": dep_id,
                        "status": "NOT_FOUND"
                    })
                    result["ready_to_execute"] = False
                elif dep_task.status != "COMPLETED":
                    result["pending_dependencies"].append({
                        "id": dep_id,
                        "title": dep_task.title,
                        "status": dep_task.status
                    })
                    result["ready_to_execute"] = False
                else:
                    result["completed_dependencies"].append({
                        "id": dep_id,
                        "title": dep_task.title,
                        "status": dep_task.status
                    })
        
        return result
    
    def add_dependency(self, db: Session, task_id: str, depends_on_id: str) -> Task:
        """
        添加任务依赖关系。
        
        Args:
            db: 数据库会话
            task_id: 任务ID
            depends_on_id: 依赖的任务ID
            
        Returns:
            更新后的任务
            
        Raises:
            TaskNotFoundError: 任务不存在时
        """
        task = self.get(db, task_id)
        if not task:
            raise TaskNotFoundError(f"任务ID不存在: {task_id}")
        
        # 检查依赖任务是否存在
        depends_on_task = self.get(db, depends_on_id)
        if not depends_on_task:
            raise TaskNotFoundError(f"依赖的任务ID不存在: {depends_on_id}")
        
        # 更新依赖列表
        depends_on = task.depends_on or []
        if depends_on_id not in depends_on:
            depends_on.append(depends_on_id)
            
            return self.update(db, db_obj=task, obj_in={"depends_on": depends_on})
        
        return task
    
    def remove_dependency(self, db: Session, task_id: str, depends_on_id: str) -> Task:
        """
        移除任务依赖关系。
        
        Args:
            db: 数据库会话
            task_id: 任务ID
            depends_on_id: 依赖的任务ID
            
        Returns:
            更新后的任务
            
        Raises:
            TaskNotFoundError: 任务不存在时
        """
        task = self.get(db, task_id)
        if not task:
            raise TaskNotFoundError(f"任务ID不存在: {task_id}")
        
        # 移除依赖
        depends_on = task.depends_on or []
        if depends_on_id in depends_on:
            depends_on.remove(depends_on_id)
            
            return self.update(db, db_obj=task, obj_in={"depends_on": depends_on})
        
        return task


class StepService(CRUDBase[Step]):
    """步骤服务类，提供特定于步骤的数据库操作"""
    
    def update_status(
        self, 
        db: Session, 
        step_id: str, 
        status: str, 
        output_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> Step:
        """
        更新步骤状态和输出数据。
        
        Args:
            db: 数据库会话
            step_id: 步骤ID
            status: 新状态
            output_data: 可选的输出数据
            error: 可选的错误信息
            
        Returns:
            更新后的步骤
            
        Raises:
            StepNotFoundError: 步骤不存在时
        """
        step = self.get(db, step_id)
        if not step:
            raise StepNotFoundError(f"步骤ID不存在: {step_id}")
        
        update_data = {"status": status, "updated_at": datetime.now()}
        
        if status == "RUNNING" and not step.started_at:
            update_data["started_at"] = datetime.now()
        
        if status == "COMPLETED":
            update_data["completed_at"] = datetime.now()
            
        if output_data:
            update_data["output_data"] = output_data
            
        if error:
            update_data["error"] = error
            
        return self.update(db, db_obj=step, obj_in=update_data)
    
    def increment_retry(self, db: Session, step_id: str) -> Step:
        """
        增加步骤的重试计数。
        
        Args:
            db: 数据库会话
            step_id: 步骤ID
            
        Returns:
            更新后的步骤
            
        Raises:
            StepNotFoundError: 步骤不存在时
        """
        step = self.get(db, step_id)
        if not step:
            raise StepNotFoundError(f"步骤ID不存在: {step_id}")
        
        retry_count = (step.retry_count or 0) + 1
        return self.update(db, db_obj=step, obj_in={"retry_count": retry_count})
    
    def get_by_task(
        self, 
        db: Session, 
        task_id: str,
        status: Optional[str] = None,
        step_type: Optional[str] = None
    ) -> List[Step]:
        """
        获取任务下的所有步骤。
        
        Args:
            db: 数据库会话
            task_id: 任务ID
            status: 可选的状态过滤
            step_type: 可选的步骤类型过滤
            
        Returns:
            步骤列表
        """
        query = db.query(Step).filter(Step.task_id == task_id)
        
        if status:
            query = query.filter(Step.status == status)
        
        if step_type:
            query = query.filter(Step.step_type == step_type)
        
        return query.order_by(Step.priority.desc(), Step.created_at).all()
    
    def get_steps_for_agent(
        self, 
        db: Session, 
        agent_type: str,
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[Step]:
        """
        获取特定智能体类型的步骤。
        
        Args:
            db: 数据库会话
            agent_type: 智能体类型
            status: 可选的状态过滤
            limit: 返回的最大记录数
            
        Returns:
            步骤列表
        """
        query = db.query(Step).filter(Step.agent_type == agent_type)
        
        if status:
            query = query.filter(Step.status == status)
        
        return query.order_by(Step.priority.desc(), Step.created_at).limit(limit).all()


class WorkflowService(CRUDBase[Workflow]):
    """工作流服务类，提供特定于工作流的数据库操作"""
    
    def get_with_checkpoints(self, db: Session, workflow_id: str) -> Optional[Workflow]:
        """
        获取工作流及其所有检查点。
        
        Args:
            db: 数据库会话
            workflow_id: 工作流ID
            
        Returns:
            找到的工作流(包含检查点)或None
            
        Raises:
            WorkflowNotFoundError: 工作流不存在时
        """
        workflow = db.query(Workflow).options(
            joinedload(Workflow.checkpoints)
        ).filter(Workflow.id == workflow_id).first()
        
        if not workflow:
            raise WorkflowNotFoundError(f"工作流ID不存在: {workflow_id}")
        
        return workflow
    
    def update_state(
        self, 
        db: Session, 
        workflow_id: str, 
        state: Dict[str, Any],
        current_node: Optional[str] = None
    ) -> Workflow:
        """
        更新工作流状态。
        
        Args:
            db: 数据库会话
            workflow_id: 工作流ID
            state: 新状态数据
            current_node: 当前节点名称
            
        Returns:
            更新后的工作流
            
        Raises:
            WorkflowNotFoundError: 工作流不存在时
        """
        workflow = self.get(db, workflow_id)
        if not workflow:
            raise WorkflowNotFoundError(f"工作流ID不存在: {workflow_id}")
        
        update_data = {"state": state, "updated_at": datetime.now()}
        
        if current_node:
            update_data["current_node"] = current_node
            
        return self.update(db, db_obj=workflow, obj_in=update_data)
    
    def update_status(self, db: Session, workflow_id: str, status: str) -> Workflow:
        """
        更新工作流状态。
        
        Args:
            db: 数据库会话
            workflow_id: 工作流ID
            status: 新状态
            
        Returns:
            更新后的工作流
            
        Raises:
            WorkflowNotFoundError: 工作流不存在时
        """
        workflow = self.get(db, workflow_id)
        if not workflow:
            raise WorkflowNotFoundError(f"工作流ID不存在: {workflow_id}")
        
        update_data = {"status": status, "updated_at": datetime.now()}
        
        if status == "RUNNING" and not workflow.started_at:
            update_data["started_at"] = datetime.now()
            
        if status in ["COMPLETED", "FAILED", "CANCELLED"]:
            update_data["completed_at"] = datetime.now()
            
        return self.update(db, db_obj=workflow, obj_in=update_data)
    
    def pause_workflow(self, db: Session, workflow_id: str) -> Workflow:
        """
        暂停工作流。
        
        Args:
            db: 数据库会话
            workflow_id: 工作流ID
            
        Returns:
            更新后的工作流
            
        Raises:
            WorkflowNotFoundError: 工作流不存在时
        """
        workflow = self.get(db, workflow_id)
        if not workflow:
            raise WorkflowNotFoundError(f"工作流ID不存在: {workflow_id}")
        
        return self.update(db, db_obj=workflow, obj_in={"is_paused": True})
    
    def resume_workflow(self, db: Session, workflow_id: str) -> Workflow:
        """
        恢复工作流。
        
        Args:
            db: 数据库会话
            workflow_id: 工作流ID
            
        Returns:
            更新后的工作流
            
        Raises:
            WorkflowNotFoundError: 工作流不存在时
        """
        workflow = self.get(db, workflow_id)
        if not workflow:
            raise WorkflowNotFoundError(f"工作流ID不存在: {workflow_id}")
        
        return self.update(db, db_obj=workflow, obj_in={"is_paused": False})
    
    def create_checkpoint(
        self, 
        db: Session, 
        workflow_id: str, 
        name: str,
        node_name: str,
        state: Dict[str, Any]
    ) -> WorkflowCheckpoint:
        """
        创建工作流检查点。
        
        Args:
            db: 数据库会话
            workflow_id: 工作流ID
            name: 检查点名称
            node_name: 节点名称
            state: 状态数据
            
        Returns:
            创建的检查点
            
        Raises:
            WorkflowNotFoundError: 工作流不存在时
        """
        # 检查工作流是否存在
        workflow = self.get(db, workflow_id)
        if not workflow:
            raise WorkflowNotFoundError(f"工作流ID不存在: {workflow_id}")
        
        # 创建检查点
        checkpoint_data = {
            "workflow_id": workflow_id,
            "name": name,
            "node_name": node_name,
            "state": state,
            "created_at": datetime.now()
        }
        
        return workflow_checkpoint_service.create(db, obj_in=checkpoint_data)


class IndustryStandardService(CRUDBase[IndustryStandard]):
    """行业标准服务类，提供特定于行业标准的数据库操作"""
    
    def get_by_industry(
        self, 
        db: Session, 
        industry_type: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[IndustryStandard]:
        """
        根据行业类型获取标准列表。
        
        Args:
            db: 数据库会话
            industry_type: 行业类型
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            行业标准列表
        """
        try:
            standards = (
                db.query(IndustryStandard)
                .filter(IndustryStandard.industry_type == industry_type)
                .order_by(IndustryStandard.standard_name)
                .offset(skip)
                .limit(limit)
                .all()
            )
            return standards
        except SQLAlchemyError as e:
            logger.error(f"查询行业标准时出错: {str(e)}")
            raise DatabaseError(f"无法查询行业标准: {str(e)}")
    
    def get_by_region(
        self, 
        db: Session, 
        region: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[IndustryStandard]:
        """
        根据地区获取标准列表。
        
        Args:
            db: 数据库会话
            region: 地区名称
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            行业标准列表
        """
        try:
            # 查询地区字段（JSON数组）包含指定地区的标准
            standards = (
                db.query(IndustryStandard)
                .filter(IndustryStandard.regions.contains([region]))
                .order_by(IndustryStandard.standard_name)
                .offset(skip)
                .limit(limit)
                .all()
            )
            return standards
        except SQLAlchemyError as e:
            logger.error(f"按地区查询行业标准时出错: {str(e)}")
            raise DatabaseError(f"无法按地区查询行业标准: {str(e)}")
    
    def search(
        self, 
        db: Session, 
        keywords: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[IndustryStandard]:
        """
        按关键词搜索标准。
        
        Args:
            db: 数据库会话
            keywords: 搜索关键词
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            行业标准列表
        """
        try:
            # 简单实现，在标准名称和描述中搜索关键词
            search_term = f"%{keywords}%"
            standards = (
                db.query(IndustryStandard)
                .filter(
                    or_(
                        IndustryStandard.standard_name.ilike(search_term),
                        IndustryStandard.description.ilike(search_term),
                        IndustryStandard.standard_code.ilike(search_term)
                    )
                )
                .order_by(IndustryStandard.standard_name)
                .offset(skip)
                .limit(limit)
                .all()
            )
            return standards
        except SQLAlchemyError as e:
            logger.error(f"搜索行业标准时出错: {str(e)}")
            raise DatabaseError(f"无法搜索行业标准: {str(e)}")
    
    def get_by_code(
        self, 
        db: Session, 
        standard_code: str
    ) -> Optional[IndustryStandard]:
        """
        根据标准代码获取标准详情。
        
        Args:
            db: 数据库会话
            standard_code: 标准代码
            
        Returns:
            行业标准或None
        """
        try:
            standard = (
                db.query(IndustryStandard)
                .filter(IndustryStandard.standard_code == standard_code)
                .first()
            )
            return standard
        except SQLAlchemyError as e:
            logger.error(f"查询标准代码时出错: {str(e)}")
            raise DatabaseError(f"无法查询标准代码: {str(e)}")
    
    def initialize_photovoltaic_standards(self, db: Session) -> List[str]:
        """
        初始化光伏行业标准数据。
        预填充基本的光伏行业标准数据，如果已存在则跳过。
        
        Args:
            db: 数据库会话
            
        Returns:
            添加的标准ID列表
        """
        try:
            # 光伏行业标准数据
            photovoltaic_standards = [
                {
                    "standard_name": "法国PPE2多年能源计划",
                    "standard_code": "PPE2-2019",
                    "industry_type": "photovoltaic",
                    "description": "法国多年能源计划(PPE2)规定了光伏产品的碳足迹要求，对于参与法国光伏招标项目的产品具有约束力。",
                    "issuing_authority": "法国生态转型部",
                    "effective_date": datetime(2019, 4, 23),
                    "expiration_date": None,
                    "regions": ["法国"],
                    "categories": ["光伏产品", "碳足迹"],
                    "metadata": {
                        "carbon_footprint_threshold": "550 kg CO2eq/kWp",
                        "calculation_method": "ECS方法",
                        "verification_requirement": "需第三方验证"
                    }
                },
                {
                    "standard_name": "欧盟碳边境调节机制",
                    "standard_code": "CBAM-2021",
                    "industry_type": "photovoltaic",
                    "description": "欧盟碳边境调节机制(CBAM)要求进口商申报碳排放量并购买对应的CBAM证书。",
                    "issuing_authority": "欧盟委员会",
                    "effective_date": datetime(2021, 7, 14),
                    "expiration_date": None,
                    "regions": ["欧盟", "法国"],
                    "categories": ["碳排放", "进口关税"],
                    "metadata": {
                        "transition_period": "2023-2025",
                        "full_implementation": "2026年起",
                        "covered_products": ["铝", "水泥", "电力", "肥料", "钢铁", "氢气", "部分有机化学品"]
                    }
                },
                {
                    "standard_name": "欧盟光伏产品生态设计指令",
                    "standard_code": "ECO-PV-2020",
                    "industry_type": "photovoltaic",
                    "description": "规定了光伏产品的生态设计要求，包括能效、材料使用和产品寿命等方面。",
                    "issuing_authority": "欧盟标准化委员会",
                    "effective_date": datetime(2020, 11, 1),
                    "expiration_date": None,
                    "regions": ["欧盟", "法国"],
                    "categories": ["光伏产品", "环保设计"],
                    "metadata": {
                        "efficiency_requirement": "最低转换效率要求",
                        "durability_standard": "最少25年设计寿命",
                        "recyclability": "至少70%可回收率"
                    }
                }
            ]
            
            added_ids = []
            
            # 遍历添加标准
            for std_data in photovoltaic_standards:
                # 检查是否已存在
                existing = (
                    db.query(IndustryStandard)
                    .filter(IndustryStandard.standard_code == std_data["standard_code"])
                    .first()
                )
                
                if not existing:
                    # 创建新标准
                    std = IndustryStandard(**std_data)
                    db.add(std)
                    db.flush()  # 刷新会话以获取ID
                    added_ids.append(std.id)
                    logger.info(f"添加光伏标准: {std.standard_name}")
            
            db.commit()
            return added_ids
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"初始化光伏标准时出错: {str(e)}")
            raise DatabaseError(f"无法初始化光伏标准: {str(e)}")


# 为每个模型创建服务实例
objective_service = ObjectiveService(Objective)
task_service = TaskService(Task)
step_service = StepService(Step)
workflow_service = WorkflowService(Workflow)
workflow_checkpoint_service = CRUDBase(WorkflowCheckpoint)
industry_standard_service = IndustryStandardService(IndustryStandard)


# 辅助函数，提供数据库会话
def get_db() -> Session:
    """
    获取数据库会话。
    
    用于依赖注入，例如FastAPI依赖项。
    
    Yields:
        数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DatabaseService:
    """临时数据库服务类，用于兼容API端点。
    
    注意：这是一个占位实现，提供与异步API兼容的接口但实际使用同步操作。
    在生产环境中应该使用正确的异步实现。
    """
    
    def __init__(self, session):
        """初始化数据库服务。
        
        Args:
            session: 数据库会话
        """
        self.session = session
        self.objective_service = ObjectiveService(Objective)
        self.task_service = TaskService(Task)
        self.step_service = StepService(Step)
        self.workflow_service = WorkflowService(Workflow)
    
    async def get_objective(self, objective_id: str):
        """获取目标信息。
        
        Args:
            objective_id: 目标ID
            
        Returns:
            目标信息
        """
        # 同步操作的简单包装
        objective = self.objective_service.get(self.session, objective_id)
        if not objective:
            raise ObjectiveNotFoundError(f"目标不存在: {objective_id}")
        
        # 转换为字典
        return {
            "id": objective.id,
            "title": objective.title,
            "description": objective.description,
            "status": objective.status,
            "created_at": objective.created_at or datetime.now(),
            "updated_at": objective.updated_at or datetime.now(),
            "user_id": objective.user_id,
            "priority": objective.priority or 2,
            "tags": objective.tags or [],
            "progress": 0.0,  # 占位值
            "estimated_completion": None,
            "task_count": 0,  # 占位值
            "completed_task_count": 0  # 占位值
        }
        
    async def create_objective(self, objective_data):
        """创建目标。
        
        Args:
            objective_data: 目标数据
            
        Returns:
            目标ID
        """
        # 同步操作的简单包装
        objective = self.objective_service.create(self.session, obj_in=objective_data)
        return objective.id
        
    async def update_objective(self, objective_id, update_data):
        """更新目标。
        
        Args:
            objective_id: 目标ID
            update_data: 更新数据
            
        Returns:
            更新后的目标信息
        """
        # 同步操作的简单包装
        objective = self.objective_service.get(self.session, objective_id)
        if not objective:
            raise ObjectiveNotFoundError(f"目标不存在: {objective_id}")
            
        updated = self.objective_service.update(self.session, db_obj=objective, obj_in=update_data)
        return updated.id
        
    # 临时实现其他方法，返回空列表或默认值
    async def get_tasks_by_objective(self, objective_id, filters=None, skip=0, limit=100):
        """获取目标下的任务列表。"""
        return []
        
    async def get_workflows_by_objective(self, objective_id):
        """获取目标关联的工作流。"""
        return []
        
    async def update_task(self, task_id, update_data):
        """更新任务信息。"""
        return task_id 