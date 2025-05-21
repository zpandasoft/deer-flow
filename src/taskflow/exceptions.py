# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
TaskFlow系统异常定义模块。

定义系统各部分使用的异常类层次结构。
"""


class TaskflowError(Exception):
    """任务系统基础异常类"""
    pass


class ObjectiveError(TaskflowError):
    """与研究目标相关的异常"""
    pass


class TaskError(TaskflowError):
    """与任务相关的异常"""
    pass


class StepError(TaskflowError):
    """与步骤相关的异常"""
    pass


class WorkflowError(TaskflowError):
    """与工作流相关的异常"""
    pass


class AgentError(TaskflowError):
    """与智能体相关的异常"""
    pass


class DatabaseError(TaskflowError):
    """数据库操作相关的异常"""
    pass


# 具体错误类型定义
class ObjectiveNotFoundError(ObjectiveError):
    """请求的研究目标不存在"""
    pass


class TaskNotFoundError(TaskError):
    """请求的任务不存在"""
    pass


class StepNotFoundError(StepError):
    """请求的步骤不存在"""
    pass


class ObjectiveValidationError(ObjectiveError):
    """目标验证失败"""
    pass


class TaskValidationError(TaskError):
    """任务验证失败"""
    pass


class StepValidationError(StepError):
    """步骤验证失败"""
    pass


class WorkflowNotFoundError(WorkflowError):
    """工作流不存在"""
    pass


class WorkflowStateError(WorkflowError):
    """工作流状态错误"""
    pass


class AgentExecutionError(AgentError):
    """智能体执行出错"""
    pass


class APIError(TaskflowError):
    """API调用相关的错误"""
    pass


class ConfigurationError(TaskflowError):
    """配置错误"""
    pass


class LLMError(TaskflowError):
    """LLM错误异常"""
    pass 