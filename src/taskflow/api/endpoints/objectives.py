# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""目标管理API端点。

提供创建、查询、管理研究目标的API接口。
"""

import asyncio
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.taskflow.api.deps import get_db, get_workflow_svc, WorkflowService
from src.taskflow.api.schemas import (
    ObjectiveCreate, 
    ObjectiveResponse, 
    ObjectiveDetail,
    OperationResponse,
    StatusEnum,
    TaskSummary,
)
from src.taskflow.db.service import DatabaseService
from src.taskflow.exceptions import ObjectiveNotFoundError

# 创建路由器
router = APIRouter(prefix="/objectives", tags=["objectives"])


@router.post("", response_model=ObjectiveResponse)
async def create_objective(
    objective: ObjectiveCreate, 
    db: DatabaseService = Depends(get_db)
):
    """创建新的研究目标并开始分解过程。
    
    Args:
        objective: 目标创建请求
        db: 数据库服务实例
        
    Returns:
        ObjectiveResponse: 创建结果，包含目标ID和状态
    """
    # 创建目标记录
    objective_data = {
        "title": objective.query,
        "description": objective.description,
        "status": StatusEnum.CREATED.value,
        "user_id": objective.user_id,
        "priority": objective.priority.value if objective.priority else 2,  # MEDIUM
        "tags": objective.tags or [],
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    
    objective_id = await db.create_objective(objective_data)
    
    # 启动工作流处理（异步）
    asyncio.create_task(
        start_objective_workflow(objective_id, objective.query, db)
    )
    
    return {
        "objective_id": objective_id,
        "status": StatusEnum.CREATED,
    }


@router.get("/{objective_id}", response_model=ObjectiveDetail)
async def get_objective(
    objective_id: str,
    db: DatabaseService = Depends(get_db),
):
    """获取研究目标详情。
    
    Args:
        objective_id: 目标ID
        db: 数据库服务实例
        
    Returns:
        ObjectiveDetail: 目标详情
        
    Raises:
        HTTPException: 当目标不存在时
    """
    try:
        objective = await db.get_objective(objective_id)
        return objective
    except ObjectiveNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {objective_id} 的目标",
        )


@router.get("/{objective_id}/tasks", response_model=List[TaskSummary])
async def get_objective_tasks(
    objective_id: str,
    status: Optional[StatusEnum] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: DatabaseService = Depends(get_db),
):
    """获取研究目标下的任务列表。
    
    Args:
        objective_id: 目标ID
        status: 过滤状态
        skip: 跳过记录数
        limit: 返回记录数限制
        db: 数据库服务实例
        
    Returns:
        List[TaskSummary]: 任务列表
        
    Raises:
        HTTPException: 当目标不存在时
    """
    try:
        # 验证目标是否存在
        await db.get_objective(objective_id)
        
        # 获取任务列表
        filters = {}
        if status:
            filters["status"] = status.value
            
        tasks = await db.get_tasks_by_objective(
            objective_id,
            filters=filters,
            skip=skip,
            limit=limit,
        )
        return tasks
    except ObjectiveNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {objective_id} 的目标",
        )


@router.get("/{objective_id}/status", response_model=ObjectiveDetail)
async def get_objective_status(
    objective_id: str,
    db: DatabaseService = Depends(get_db),
):
    """获取研究目标当前状态。
    
    Args:
        objective_id: 目标ID
        db: 数据库服务实例
        
    Returns:
        ObjectiveDetail: 目标详情，包含状态信息
        
    Raises:
        HTTPException: 当目标不存在时
    """
    try:
        objective = await db.get_objective(objective_id)
        return objective
    except ObjectiveNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {objective_id} 的目标",
        )


@router.post("/{objective_id}/cancel", response_model=OperationResponse)
async def cancel_objective(
    objective_id: str,
    db: DatabaseService = Depends(get_db),
    workflow_service: WorkflowService = Depends(get_workflow_svc),
):
    """取消研究目标执行。
    
    Args:
        objective_id: 目标ID
        db: 数据库服务实例
        workflow_service: 工作流服务实例
        
    Returns:
        OperationResponse: 操作结果
        
    Raises:
        HTTPException: 当目标不存在或无法取消时
    """
    try:
        # 获取目标信息
        objective = await db.get_objective(objective_id)
        
        # 检查是否可以取消
        if objective["status"] in [
            StatusEnum.COMPLETED.value,
            StatusEnum.FAILED.value,
            StatusEnum.CANCELLED.value,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无法取消状态为 {objective['status']} 的目标",
            )
        
        # 获取关联的工作流
        workflows = await db.get_workflows_by_objective(objective_id)
        if not workflows:
            # 如果没有关联工作流，直接更新目标状态
            await db.update_objective(
                objective_id,
                {"status": StatusEnum.CANCELLED.value, "updated_at": datetime.now()},
            )
        else:
            # 取消所有关联工作流
            for workflow in workflows:
                await workflow_service.cancel_workflow(workflow["id"])
                
            # 更新目标状态
            await db.update_objective(
                objective_id,
                {"status": StatusEnum.CANCELLED.value, "updated_at": datetime.now()},
            )
            
            # 获取所有未完成的任务
            active_tasks = await db.get_tasks_by_objective(
                objective_id,
                filters={
                    "status_in": [
                        StatusEnum.CREATED.value,
                        StatusEnum.PENDING.value,
                        StatusEnum.RUNNING.value,
                    ]
                },
            )
            
            # 取消所有未完成的任务
            for task in active_tasks:
                await db.update_task(
                    task["id"],
                    {"status": StatusEnum.CANCELLED.value, "updated_at": datetime.now()},
                )
        
        return {
            "success": True,
            "message": f"成功取消ID为 {objective_id} 的目标",
            "data": {"objective_id": objective_id},
        }
    except ObjectiveNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {objective_id} 的目标",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取消目标时发生错误: {str(e)}",
        )


async def start_objective_workflow(
    objective_id: str,
    query: str,
    db: DatabaseService,
):
    """启动目标分解工作流（异步执行）。
    
    Args:
        objective_id: 目标ID
        query: 用户查询
        db: 数据库服务实例
    """
    try:
        # 更新目标状态为处理中
        await db.update_objective(
            objective_id,
            {"status": StatusEnum.RUNNING.value, "updated_at": datetime.now()},
        )
        
        # 获取工作流服务
        workflow_service = get_workflow_svc()
        
        # 创建目标分解工作流
        workflow_id = await workflow_service.create_workflow(
            "decomposition",
            {
                "objective_id": objective_id,
                "query": query,
            }
        )
        
        # 运行工作流 - 简化实现，不实际运行
        # await workflow_service.run_workflow(workflow_id)
    except Exception as e:
        # 发生错误时，更新目标状态为失败
        await db.update_objective(
            objective_id,
            {
                "status": StatusEnum.FAILED.value, 
                "updated_at": datetime.now(),
                "error": str(e),
            },
        ) 