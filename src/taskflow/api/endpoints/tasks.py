# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""任务管理API端点。

提供查询、管理任务和步骤的API接口。
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.taskflow.api.deps import get_db
from src.taskflow.api.schemas import (
    TaskDetail, 
    StepSummary,
    StepDetail,
    StepResult,
    StatusEnum,
)
from src.taskflow.db.service import DatabaseService
from src.taskflow.exceptions import TaskNotFoundError, StepNotFoundError

# 创建路由器
router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: str,
    db: DatabaseService = Depends(get_db),
):
    """获取任务详情。
    
    Args:
        task_id: 任务ID
        db: 数据库服务实例
        
    Returns:
        TaskDetail: 任务详情
        
    Raises:
        HTTPException: 当任务不存在时
    """
    try:
        task = await db.get_task(task_id)
        return task
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {task_id} 的任务",
        )


@router.get("/tasks/{task_id}/steps", response_model=List[StepSummary])
async def get_task_steps(
    task_id: str,
    status: Optional[StatusEnum] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: DatabaseService = Depends(get_db),
):
    """获取任务下的步骤列表。
    
    Args:
        task_id: 任务ID
        status: 过滤状态
        skip: 跳过记录数
        limit: 返回记录数限制
        db: 数据库服务实例
        
    Returns:
        List[StepSummary]: 步骤列表
        
    Raises:
        HTTPException: 当任务不存在时
    """
    try:
        # 验证任务是否存在
        await db.get_task(task_id)
        
        # 获取步骤列表
        filters = {}
        if status:
            filters["status"] = status.value
            
        steps = await db.get_steps_by_task(
            task_id,
            filters=filters,
            skip=skip,
            limit=limit,
        )
        return steps
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {task_id} 的任务",
        )


@router.get("/steps/{step_id}", response_model=StepDetail)
async def get_step(
    step_id: str,
    db: DatabaseService = Depends(get_db),
):
    """获取步骤详情。
    
    Args:
        step_id: 步骤ID
        db: 数据库服务实例
        
    Returns:
        StepDetail: 步骤详情
        
    Raises:
        HTTPException: 当步骤不存在时
    """
    try:
        step = await db.get_step(step_id)
        return step
    except StepNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {step_id} 的步骤",
        )


@router.get("/steps/{step_id}/results", response_model=StepResult)
async def get_step_results(
    step_id: str,
    db: DatabaseService = Depends(get_db),
):
    """获取步骤执行结果。
    
    Args:
        step_id: 步骤ID
        db: 数据库服务实例
        
    Returns:
        StepResult: 步骤执行结果
        
    Raises:
        HTTPException: 当步骤不存在或尚未完成时
    """
    try:
        # 获取步骤信息
        step = await db.get_step(step_id)
        
        # 检查步骤是否已完成
        if step["status"] != StatusEnum.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"步骤 {step_id} 尚未完成，当前状态: {step['status']}",
            )
        
        # 获取步骤结果
        result = await db.get_step_result(step_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到步骤 {step_id} 的执行结果",
            )
        
        return {
            "step_id": step_id,
            "status": StatusEnum(step["status"]),
            "data": result["data"],
            "created_at": result["created_at"],
            "execution_time": result["execution_time"],
        }
    except StepNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {step_id} 的步骤",
        ) 