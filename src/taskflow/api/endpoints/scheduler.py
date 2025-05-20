# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""调度器API端点。

提供获取调度器状态、资源使用情况和调度任务的API接口。
"""

import psutil
from fastapi import APIRouter, Depends, HTTPException, status

from src.taskflow.api.deps import get_scheduler_service
from src.taskflow.api.schemas import (
    SchedulerStatus,
    ResourceUsage,
    StepSchedule,
    ScheduleResponse,
)
from src.taskflow.scheduler.scheduler import TaskScheduler

# 创建路由器
router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/status", response_model=SchedulerStatus)
async def get_scheduler_status(
    scheduler: TaskScheduler = Depends(get_scheduler_service),
):
    """获取调度器状态。
    
    Args:
        scheduler: 调度器服务实例
        
    Returns:
        SchedulerStatus: 调度器状态信息
    """
    status = await scheduler.get_status()
    return {
        "active": status["active"],
        "worker_count": status["worker_count"],
        "busy_workers": status["busy_workers"],
        "queue_size": status["queue_size"],
        "processed_count": status["processed_count"],
        "failed_count": status["failed_count"],
    }


@router.get("/resources", response_model=ResourceUsage)
async def get_resource_usage():
    """获取系统资源使用情况。
    
    Returns:
        ResourceUsage: 资源使用统计
    """
    try:
        # 获取CPU使用率
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # 获取内存使用率
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # 获取磁盘使用率
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        
        # 获取网络IO统计
        net_io = psutil.net_io_counters()
        
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_percent": disk_percent,
            "network_sent": net_io.bytes_sent,
            "network_received": net_io.bytes_recv,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取资源使用情况时发生错误: {str(e)}",
        )


@router.post("/steps/schedule", response_model=ScheduleResponse)
async def schedule_steps(
    request: StepSchedule,
    scheduler: TaskScheduler = Depends(get_scheduler_service),
):
    """调度步骤执行。
    
    Args:
        request: 调度请求，包含步骤ID列表和优先级
        scheduler: 调度器服务实例
        
    Returns:
        ScheduleResponse: 调度结果
        
    Raises:
        HTTPException: 当调度失败时
    """
    try:
        # 调度步骤执行
        schedule_ids = await scheduler.schedule_steps(
            step_ids=request.step_ids,
            priority=request.priority.value if request.priority else 2,  # MEDIUM
        )
        
        return {
            "schedule_ids": schedule_ids,
            "status": "SCHEDULED",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"调度步骤执行时发生错误: {str(e)}",
        ) 