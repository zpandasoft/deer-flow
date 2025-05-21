# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""工作流管理API端点。

提供查询、管理工作流和检查点的API接口。
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.taskflow.api.deps import get_db, get_workflow_svc, WorkflowService
from src.taskflow.api.schemas import (
    WorkflowState,
    CheckpointSummary,
    OperationResponse,
)
from src.taskflow.db.service import DatabaseService
from src.taskflow.exceptions import WorkflowNotFoundError, WorkflowStateError

# 创建路由器
router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/{workflow_id}/state", response_model=WorkflowState)
async def get_workflow_state(
    workflow_id: str,
    db: DatabaseService = Depends(get_db),
):
    """获取工作流当前状态。
    
    Args:
        workflow_id: 工作流ID
        db: 数据库服务实例
        
    Returns:
        WorkflowState: 工作流状态
        
    Raises:
        HTTPException: 当工作流不存在时
    """
    try:
        workflow = await db.get_workflow(workflow_id)
        return workflow
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {workflow_id} 的工作流",
        )


@router.post("/{workflow_id}/pause", response_model=OperationResponse)
async def pause_workflow(
    workflow_id: str,
    workflow_service: WorkflowService = Depends(get_workflow_svc),
):
    """暂停工作流执行。
    
    Args:
        workflow_id: 工作流ID
        workflow_service: 工作流服务实例
        
    Returns:
        OperationResponse: 操作结果
        
    Raises:
        HTTPException: 当工作流不存在或无法暂停时
    """
    try:
        success = await workflow_service.pause_workflow(workflow_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法暂停工作流，可能工作流已经完成或已经暂停",
            )
        return {
            "success": True,
            "message": f"成功暂停ID为 {workflow_id} 的工作流",
            "data": {"workflow_id": workflow_id},
        }
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {workflow_id} 的工作流",
        )
    except WorkflowStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"暂停工作流时发生错误: {str(e)}",
        )


@router.post("/{workflow_id}/resume", response_model=OperationResponse)
async def resume_workflow(
    workflow_id: str,
    workflow_service: WorkflowService = Depends(get_workflow_svc),
):
    """恢复工作流执行。
    
    Args:
        workflow_id: 工作流ID
        workflow_service: 工作流服务实例
        
    Returns:
        OperationResponse: 操作结果
        
    Raises:
        HTTPException: 当工作流不存在或无法恢复时
    """
    try:
        success = await workflow_service.resume_workflow(workflow_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法恢复工作流，可能工作流未暂停或已经完成",
            )
        return {
            "success": True,
            "message": f"成功恢复ID为 {workflow_id} 的工作流",
            "data": {"workflow_id": workflow_id},
        }
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {workflow_id} 的工作流",
        )
    except WorkflowStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"恢复工作流时发生错误: {str(e)}",
        )


@router.get("/{workflow_id}/checkpoints", response_model=List[CheckpointSummary])
async def get_workflow_checkpoints(
    workflow_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: DatabaseService = Depends(get_db),
):
    """获取工作流检查点列表。
    
    Args:
        workflow_id: 工作流ID
        skip: 跳过记录数
        limit: 返回记录数限制
        db: 数据库服务实例
        
    Returns:
        List[CheckpointSummary]: 检查点列表
        
    Raises:
        HTTPException: 当工作流不存在时
    """
    try:
        # 验证工作流是否存在
        await db.get_workflow(workflow_id)
        
        # 获取检查点列表
        checkpoints = await db.get_checkpoints_by_workflow(
            workflow_id,
            skip=skip,
            limit=limit,
        )
        return checkpoints
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到ID为 {workflow_id} 的工作流",
        )


@router.post("/checkpoints/{checkpoint_id}/restore", response_model=OperationResponse)
async def restore_from_checkpoint(
    checkpoint_id: str,
    workflow_service: WorkflowService = Depends(get_workflow_svc),
    db: DatabaseService = Depends(get_db),
):
    """从检查点恢复工作流。
    
    Args:
        checkpoint_id: 检查点ID
        workflow_service: 工作流服务实例
        db: 数据库服务实例
        
    Returns:
        OperationResponse: 操作结果，包含恢复后的工作流ID
        
    Raises:
        HTTPException: 当检查点不存在或恢复失败时
    """
    try:
        # 获取检查点信息
        checkpoint = await db.get_checkpoint(checkpoint_id)
        
        # 从检查点恢复工作流
        new_workflow_id = await workflow_service.restore_from_checkpoint(checkpoint_id)
        
        return {
            "success": True,
            "message": f"成功从检查点 {checkpoint_id} 恢复工作流",
            "data": {
                "workflow_id": new_workflow_id,
                "checkpoint_id": checkpoint_id,
                "original_workflow_id": checkpoint["workflow_id"],
            },
        }
    except WorkflowStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"从检查点恢复工作流时发生错误: {str(e)}",
        ) 