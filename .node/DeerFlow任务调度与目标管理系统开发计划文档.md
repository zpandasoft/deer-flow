# DeerFlow任务调度与目标管理系统开发计划文档

## 1. 项目概述

本项目旨在基于DeerFlow框架开发一个任务调度与目标管理系统，能够分解复杂研究目标、管理任务执行流程，并通过多智能体协作完成目标。
## 2. 项目目标

- 开发基于LangGraph的状态驱动多智能体工作流系统
- 实现复杂研究目标的结构化分解和管理
- 构建任务的自动调度和资源分配机制
- 实现智能体间的高效协作和状态共享
- 提供与DeerFlow无缝集成的接口和扩展

## 3. 代码规范

### 3.1 代码风格与组织

- **版权声明**：所有源文件顶部必须包含统一的版权声明
  ```python
  # Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
  # SPDX-License-Identifier: MIT
  ```

- **导入顺序**：遵循以下导入顺序
  1. 标准库导入
  2. 第三方库导入
  3. 本地应用/库导入
  ```python
  # 标准库
  import asyncio
  import logging
  
  # 第三方库
  from langgraph.graph import StateGraph, START, END
  
  # 本地应用
  from src.prompts import apply_prompt_template
  ```

- **模块化**：按功能明确分离代码
  - 智能体代码位于 `src/agents/`
  - 配置代码位于 `src/config/`
  - 工作流图定义位于 `src/graph/`
  - 提示词模板位于 `src/prompts/`
  - 工具函数位于 `src/tools/`
  - 通用功能在 `src/utils/`

- **类和函数设计**：
  - 遵循单一职责原则
  - 类方法顺序：先静态方法，后实例方法
  - 相关功能应该分组在一起
  - 使用类型注解

### 3.2 命名与文档约定

- **变量命名规范**：
  - 类名使用 `PascalCase`：`ObjectiveDecomposerAgent`
  - 函数名和变量名使用 `snake_case`：`decompose_objective`
  - 常量使用 `UPPER_CASE`：`MAX_RETRY_COUNT`
  - 私有变量和方法以下划线开头：`_process_response`
  - 临时变量使用有意义的名称，避免使用 `temp`, `x`, `y`

- **文档字符串规范**：使用 Google 风格的文档字符串
  ```python
  def analyze_task(task_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
      """分析任务内容和相关信息。
      
      Args:
          task_id: 任务ID
          context: 任务上下文信息
      
      Returns:
          任务分析结果，包含下一步建议
          
      Raises:
          TaskNotFoundError: 当任务ID不存在时
          AnalysisError: 分析失败时
      """
  ```

- **注释规范**：
  - 解释"为什么"而不是"做什么"
  - 使用中文注释
  - 对复杂算法或业务逻辑添加详细注释
  - 临时解决方案应标记 `# TODO: 在 v2.0 中实现更高效的方法`

- **文件组织**：
  - 每个文件开头包含版权声明
  - 随后是模块级文档字符串，描述文件用途
  - 然后是导入语句
  - 最后是实现代码
  ```python
  # Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
  # SPDX-License-Identifier: MIT
  
  """TaskAnalyzer 负责分解和分析任务结构。
  
  该模块提供任务分析功能，能够识别任务类型、依赖关系，
  并推荐合适的执行策略。
  """
  
  # 标准库导入
  import json
  from typing import Dict, List, Any, Optional
  
  # 第三方库导入
  import pydantic
  
  # 本地导入
  from src.utils.logger import get_logger
  ```

### 3.3 错误处理与日志

- **错误处理原则**：
  - 使用具体的异常类而非通用异常
  - 在适当的抽象层次处理错误
  - 记录详细错误信息
  - 对用户友好地处理错误

- **异常层次结构**：
  ```python
  # 基础异常
  class TaskflowError(Exception):
      """任务系统基础异常类"""
      pass
  
  # 子系统异常
  class ObjectiveError(TaskflowError):
      """与研究目标相关的异常"""
      pass
  
  class TaskError(TaskflowError):
      """与任务相关的异常"""
      pass
  
  # 具体错误类型
  class ObjectiveNotFoundError(ObjectiveError):
      """请求的研究目标不存在"""
      pass
  
  class TaskValidationError(TaskError):
      """任务验证失败"""
      pass
  ```

- **日志记录**：
  - 使用结构化日志格式
  - 包含上下文信息
  - 使用适当的日志级别
  - 敏感信息必须脱敏
  ```python
  logger = get_logger(__name__)
  
  def process_task(task_id: str) -> None:
      """处理任务"""
      logger.info("开始处理任务", extra={"task_id": task_id})
      try:
          task = get_task(task_id)
          result = execute_task(task)
          logger.info("任务处理完成", extra={"task_id": task_id, "status": "success"})
      except TaskNotFoundError:
          logger.warning("任务不存在", extra={"task_id": task_id})
          raise
      except Exception as e:
          logger.error("任务处理失败", 
                       extra={"task_id": task_id, "error": str(e), "error_type": type(e).__name__})
          raise TaskProcessingError(f"处理任务 {task_id} 失败") from e
  ```

- **重试机制**：
  - 对外部服务调用实现重试逻辑
  - 使用指数退避策略
  - 避免过度重试
  ```python
  @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
  async def call_llm_api(prompt: str) -> str:
      """调用LLM API，自动重试"""
      try:
          response = await llm_client.completion(prompt=prompt)
          return response.text
      except APIError as e:
          logger.warning("LLM API调用失败，准备重试", extra={"error": str(e)})
          raise  # 触发重试
  ```

### 3.4 测试规范

- **测试框架**：使用pytest进行单元测试和集成测试

- **测试文件组织**：
  - 单元测试位于 `tests/unit/` 目录
  - 集成测试位于 `tests/integration/` 目录
  - 测试文件命名格式为 `test_*.py`

- **测试覆盖率**：
  - 核心组件测试覆盖率不低于85%
  - 非核心组件测试覆盖率不低于70%

- **测试类型**：
  - 单元测试：测试独立组件的功能
  - 集成测试：测试组件间的交互
  - 端到端测试：验证完整流程

- **测试最佳实践**：
  - 使用fixture装载测试数据
  - 模拟外部依赖
  - 单元测试应该快速、独立和可重复
  - 编写对边界条件和错误路径的测试

- **测试示例**：
  ```python
  import pytest
  from unittest.mock import MagicMock
  from src.agents.objective_decomposer import ObjectiveDecomposerAgent
  
  @pytest.fixture
  def mock_llm():
      """创建模拟LLM"""
      mock = MagicMock()
      mock.invoke.return_value = '{"tasks": [{"id": "task-1", "title": "分析PPE2要求"}]}'
      return mock
  
  def test_objective_decomposition(mock_llm):
      """测试目标分解功能"""
      agent = ObjectiveDecomposerAgent(llm=mock_llm)
      state = {"query": "研究光伏出口法国的要求"}
      
      result = agent(state)
      
      assert "tasks" in result
      assert len(result["tasks"]) > 0
      assert result["tasks"][0]["title"] == "分析PPE2要求"
  ```

## 4. 项目结构

### 4.1 目录结构

```
src/
├── taskflow/                     # 任务调度与目标管理系统核心代码
│   ├── __init__.py
│   ├── agents/                   # 智能体实现
│   │   ├── __init__.py
│   │   ├── base.py               # 基础智能体抽象类
│   │   ├── context_analyzer.py   # 上下文分析智能体
│   │   ├── objective_decomposer.py   # 目标分解智能体
│   │   ├── task_analyzer.py      # 任务分析智能体
│   │   ├── research_agent.py     # 研究智能体
│   │   ├── processing_agent.py   # 处理智能体
│   │   ├── quality_evaluator.py  # 质量评估智能体
│   │   ├── synthesis_agent.py    # 合成智能体
│   │   └── error_handler.py      # 错误处理智能体
│   │
│   ├── config/                   # 配置管理
│   │   ├── __init__.py
│   │   ├── task_config.py        # 任务配置
│   │   └── scheduler_config.py   # 调度器配置
│   │
│   ├── db/                       # 数据库交互
│   │   ├── __init__.py
│   │   ├── models.py             # 数据模型定义
│   │   └── service.py            # 数据库服务
│   │
│   ├── graph/                    # 工作流图实现
│   │   ├── __init__.py
│   │   ├── builder.py            # 工作流图构建器
│   │   ├── nodes.py              # 工作流节点定义
│   │   ├── routers.py            # 条件路由函数
│   │   └── types.py              # 工作流类型定义
│   │
│   ├── prompts/                  # 提示词模板
│   │   ├── __init__.py
│   │   ├── context_analysis.py   # 上下文分析提示词
│   │   ├── objective_decompose.py # 目标分解提示词
│   │   ├── task_analysis.py      # 任务分析提示词
│   │   └── templates.py          # 通用模板函数
│   │
│   ├── scheduler/                # 任务调度器
│   │   ├── __init__.py
│   │   ├── dispatcher.py         # 任务分发器
│   │   ├── priority.py           # 优先级管理
│   │   ├── queue.py              # 任务队列实现
│   │   └── worker.py             # 工作线程池
│   │
│   ├── api/                      # API接口
│   │   ├── __init__.py
│   │   ├── endpoints/            # API端点
│   │   │   ├── __init__.py
│   │   │   ├── objectives.py     # 目标管理API
│   │   │   ├── tasks.py          # 任务管理API
│   │   │   └── status.py         # 状态查询API
│   │   ├── schemas.py            # API请求/响应模型
│   │   ├── deps.py               # 依赖注入
│   │   └── app.py                # FastAPI应用
│   │
│   ├── tools/                    # 工具函数
│   │   ├── __init__.py
│   │   ├── document_processor.py # 文档处理工具
│   │   ├── web_search.py         # 网络搜索工具
│   │   └── data_extractor.py     # 数据提取工具
│   │
│   ├── utils/                    # 通用工具
│   │   ├── __init__.py
│   │   ├── logger.py             # 日志工具
│   │   ├── metrics.py            # 性能指标收集
│   │   └── validation.py         # 数据验证
│   │
│   ├── exceptions.py             # 异常定义
│   └── main.py                   # 应用入口
│
├── tests/                        # 测试代码
│   ├── __init__.py
│   ├── conftest.py               # 测试配置
│   ├── unit/                     # 单元测试
│   │   ├── __init__.py
│   │   ├── agents/               # 智能体测试
│   │   ├── graph/                # 工作流图测试
│   │   └── scheduler/            # 调度器测试
│   ├── integration/              # 集成测试
│   │   ├── __init__.py
│   │   ├── workflow_tests.py     # 工作流集成测试
│   │   └── api_tests.py          # API集成测试
│   └── fixtures/                 # 测试数据
│       ├── __init__.py
│       ├── mock_responses.py     # 模拟响应数据
│       └── test_data.py          # 测试数据集
│
├── scripts/                      # 管理脚本
│   ├── migrations/               # 数据库迁移脚本
│   ├── init_db.py                # 数据库初始化
│   └── seed_data.py              # 填充测试数据
│
├── docs/                         # 文档
│   ├── api/                      # API文档
│   ├── architecture/             # 架构文档
│   └── examples/                 # 使用示例
│
├── alembic/                      # 数据库迁移配置
│   ├── versions/                 # 迁移版本
│   ├── env.py                    # 迁移环境
│   └── alembic.ini               # 迁移配置
│
├── requirements/                 # 依赖管理
│   ├── base.txt                  # 基础依赖
│   ├── dev.txt                   # 开发依赖
│   └── prod.txt                  # 生产依赖
│
├── .env.example                  # 环境变量示例
├── pyproject.toml                # 项目配置
├── docker-compose.yml            # Docker配置
├── Dockerfile                    # Docker构建文件
└── README.md                     # 项目说明
```

### 4.2 核心模块说明

#### 4.2.1 智能体系统 (`src/taskflow/agents/`)

智能体系统是任务调度与目标管理的核心，包含多种专用智能体：

- **BaseAgent (`base.py`)**：
  - 智能体抽象基类，定义通用接口和工具集
  - 提供上下文管理、输入格式化和输出解析
  - 实现重试逻辑和错误处理

- **ContextAnalyzerAgent (`context_analyzer.py`)**：
  - 分析用户查询和相关上下文
  - 识别研究领域、关键概念和目标类型
  - 提供结构化的上下文信息

- **ObjectiveDecomposerAgent (`objective_decomposer.py`)**：
  - 将复杂研究目标分解为子目标和具体任务
  - 建立任务间的依赖关系
  - 确定任务优先级和执行顺序

- **TaskAnalyzerAgent (`task_analyzer.py`)**：
  - 分析任务要求和复杂度
  - 确定任务类型（研究、处理、合成等）
  - 推荐适合的处理智能体和策略

- **ResearchAgent (`research_agent.py`)**：
  - 执行信息收集和研究任务
  - 查询和分析外部资源
  - 生成研究报告和发现

- **ProcessingAgent (`processing_agent.py`)**：
  - 处理和转换数据
  - 实现特定领域的处理逻辑
  - 生成中间处理结果

- **QualityEvaluatorAgent (`quality_evaluator.py`)**：
  - 评估任务执行质量
  - 检测错误和不一致性
  - 提供改进建议

- **SynthesisAgent (`synthesis_agent.py`)**：
  - 汇总多任务结果
  - 生成综合报告和结论
  - 确保内容的一致性和完整性

- **ErrorHandlerAgent (`error_handler.py`)**：
  - 处理执行过程中的异常情况
  - 诊断错误原因
  - 推荐恢复策略

#### 4.2.2 工作流图系统 (`src/taskflow/graph/`)

工作流图系统基于LangGraph实现，管理智能体之间的状态转换和交互：

- **工作流图构建器 (`builder.py`)**：
  - 构建工作流图和节点关系
  - 定义状态转换逻辑
  - 注册条件路由和节点函数

- **工作流节点 (`nodes.py`)**：
  - 定义工作流节点函数
  - 实现状态转换逻辑
  - 调用相应的智能体处理逻辑

- **条件路由 (`routers.py`)**：
  - 实现工作流分支决策函数
  - 基于状态内容确定下一节点
  - 处理特殊路由条件

- **工作流类型 (`types.py`)**：
  - 定义工作流状态类型
  - 实现状态验证和转换
  - 提供序列化和反序列化功能

#### 4.2.3 任务调度系统 (`src/taskflow/scheduler/`)

任务调度系统负责管理任务队列、优先级和资源分配：

- **任务分发器 (`dispatcher.py`)**：
  - 将任务分发给适当的工作线程
  - 管理任务状态和生命周期
  - 处理任务完成和失败事件

- **优先级管理 (`priority.py`)**：
  - 实现任务优先级算法
  - 动态调整任务优先级
  - 确保关键任务得到及时处理

- **任务队列 (`queue.py`)**：
  - 实现高效的优先队列
  - 支持任务暂停和恢复
  - 提供队列状态监控

- **工作线程池 (`worker.py`)**：
  - 管理工作线程资源
  - 实现任务执行和监控
  - 处理线程异常和恢复

#### 4.2.4 数据库服务 (`src/taskflow/db/`)

数据库服务负责数据持久化和查询：

- **数据模型 (`models.py`)**：
  - 定义ORM模型（目标、任务、步骤等）
  - 实现模型关系和约束
  - 提供数据验证和转换方法

- **数据库服务 (`service.py`)**：
  - 提供CRUD操作接口
  - 实现复杂查询和事务
  - 管理数据库连接和会话

#### 4.2.5 API接口 (`src/taskflow/api/`)

API接口提供RESTful服务，允许外部系统与任务系统交互：

- **API应用 (`app.py`)**：
  - 配置FastAPI应用
  - 注册路由和中间件
  - 配置CORS和安全策略

- **API端点 (`endpoints/`)**：
  - 实现RESTful API接口
  - 处理请求验证和响应格式化
  - 实现业务逻辑和服务调用

- **请求/响应模型 (`schemas.py`)**：
  - 定义API输入输出模型
  - 实现数据验证和转换
  - 提供模型文档

## 5. 实施计划

### 5.1 阶段一：基础设施和数据模型（第1-2周）

**目标**：完成系统基础结构搭建和数据模型定义。

**关键任务**：
1. 设计和实现数据模型（Objective、Task、Step等）
2. 配置PostgreSQL数据库和SQLAlchemy ORM
3. 实现基本的数据库服务接口
4. 搭建项目骨架和目录结构
5. 设置日志、配置和基础工具函数

**具体步骤**：
- 第1周：
  - 分析需求，确定数据模型结构
  - 配置数据库连接和ORM映射
  - 编写基础模型类和验证器
- 第2周：
  - 实现数据库服务接口
  - 完成数据库迁移脚本
  - 搭建基础工具和配置模块
  - 编写单元测试

**交付物**：
- 完整的数据模型和数据库服务
- 基础工具和配置模块
- 单元测试覆盖率 > 80%

### 5.2 阶段二：多智能体系统实现（第3-5周）

**目标**：实现多智能体系统的核心组件和提示词模板。

**关键任务**：
1. 实现BaseAgent基类和通用功能
2. 实现所有专用智能体（分析、执行、评估、协调）
3. 开发智能体提示词模板
4. 完成智能体单元测试和集成测试

**具体步骤**：
- 第3周：
  - 实现BaseAgent基类和核心功能
  - 开发ContextAnalyzerAgent和ObjectiveDecomposerAgent
  - 编写相应的提示词模板
- 第4周：
  - 开发TaskAnalyzerAgent、ResearchAgent和ProcessingAgent
  - 实现针对不同任务类型的处理逻辑
  - 编写相应的提示词模板
- 第5周：
  - 开发QualityEvaluatorAgent、SynthesisAgent和ErrorHandlerAgent
  - 实现智能体协作机制
  - 编写单元测试和集成测试

**交付物**：
- 完整的智能体实现代码
- 提示词模板库
- 单元测试和集成测试

### 5.3 阶段三：任务调度与管理系统（第6-8周）

**目标**：实现任务调度系统和工作流引擎。

**关键任务**：
1. 实现TaskScheduler核心调度器
2. 开发TaskExecutor任务执行器
3. 实现ResourceManager资源管理器
4. 构建工作流图和状态管理机制
5. 开发并发执行和同步机制

**具体步骤**：
- 第6周：
  - 实现TaskScheduler核心组件
  - 开发基本的任务调度和管理功能
  - 构建工作流状态类型
- 第7周：
  - 实现TaskExecutor和执行监控
  - 开发ResourceManager资源分配
  - 构建工作流图和节点函数
- 第8周：
  - 实现并发执行和同步机制
  - 开发错误处理和恢复功能
  - 集成测试调度系统和工作流

**交付物**：
- 功能完整的任务调度系统
- 基于LangGraph的工作流图实现
- 资源管理和并发控制机制
- 系统集成测试

### 5.4 阶段四：API与集成接口（第9-10周）

**目标**：开发API接口和外部服务集成。

**关键任务**：
1. 设计和实现RESTful API接口
2. 集成Dify API服务
3. 开发爬虫服务和行业标准服务
4. 实现客户端SDK

**具体步骤**：
- 第9周：
  - 设计API接口规范
  - 实现核心API路由和控制器
  - 开发API请求和响应模型
- 第10周：
  - 开发DifyService和外部API集成
  - 实现爬虫服务和标准服务
  - 开发客户端SDK和集成示例

**交付物**：
- 完整的API接口文档和实现
- 外部服务集成模块
- 客户端SDK和示例代码

### 5.5 阶段五：测试与优化（第11-12周）

**目标**：进行系统测试、性能优化和bug修复。

**关键任务**：
1. 执行全面的系统测试
2. 进行性能测试和优化
3. 修复发现的bug和问题
4. 完善文档和示例

**具体步骤**：
- 第11周：
  - 进行全面的系统功能测试
  - 执行压力测试和性能分析
  - 识别和修复关键bug
- 第12周：
  - 进行系统优化和性能提升
  - 完善文档和使用指南
  - 准备示例和演示

**交付物**：
- 测试报告和性能分析
- 优化后的系统代码
- 完整的文档和示例

### 5.6 阶段六：部署与文档（第13周）

**目标**：完成系统部署和文档准备。

**关键任务**：
1. 准备部署脚本和配置
2. 完成用户文档和开发文档
3. 准备演示和培训材料
4. 系统上线和维护计划

**具体步骤**：
- 准备Docker容器和部署脚本
- 完成API文档和用户指南
- 准备系统演示和培训材料
- 制定维护和监控计划

**交付物**：
- 部署配置和脚本
- 完整的文档集
- 培训和演示材料
- 维护计划

## 6. 接口设计

### 6.1 核心API

系统将提供以下RESTful API接口，用于与外部系统交互：

#### 6.1.1 目标管理API

| 端点 | 方法 | 描述 | 参数 | 返回 |
|------|------|------|------|------|
| `/api/v1/objectives` | POST | 创建新的研究目标 | `query`(必填): 用户查询<br>`user_id`: 用户ID<br>`priority`: 优先级<br>`tags`: 标签列表 | 目标ID和初始状态 |
| `/api/v1/objectives/{objective_id}` | GET | 获取目标详情 | `objective_id`(必填): 目标ID | 目标完整信息 |
| `/api/v1/objectives/{objective_id}/status` | GET | 获取目标状态 | `objective_id`(必填): 目标ID | 目标状态信息 |
| `/api/v1/objectives/{objective_id}/cancel` | POST | 取消目标执行 | `objective_id`(必填): 目标ID | 操作结果 |

**示例实现**:
```python
@router.post("/objectives", response_model=ObjectiveResponse)
async def create_objective(objective: ObjectiveCreate, db: DatabaseService = Depends(get_db)):
    """创建新的研究目标并开始分解过程"""
    objective_id = await db.create_objective({
        "title": objective.query,
        "description": objective.description,
        "status": "CREATED",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    })
    
    # 启动工作流处理
    asyncio.create_task(start_objective_workflow(objective_id, objective.query))
    
    return {"objective_id": objective_id, "status": "CREATED"}
```

#### 6.1.2 任务和步骤API

| 端点 | 方法 | 描述 | 参数 | 返回 |
|------|------|------|------|------|
| `/api/v1/objectives/{objective_id}/tasks` | GET | 获取目标下的任务列表 | `objective_id`(必填): 目标ID<br>`status`: 过滤状态 | 任务列表 |
| `/api/v1/tasks/{task_id}` | GET | 获取任务详情 | `task_id`(必填): 任务ID | 任务完整信息 |
| `/api/v1/tasks/{task_id}/steps` | GET | 获取任务下的步骤列表 | `task_id`(必填): 任务ID<br>`status`: 过滤状态 | 步骤列表 |
| `/api/v1/steps/{step_id}` | GET | 获取步骤详情 | `step_id`(必填): 步骤ID | 步骤完整信息 |
| `/api/v1/steps/{step_id}/results` | GET | 获取步骤执行结果 | `step_id`(必填): 步骤ID | 步骤执行结果 |

**示例实现**:
```python
@router.get("/tasks/{task_id}", response_model=TaskDetail)
async def get_task(task_id: str, db: DatabaseService = Depends(get_db)):
    """获取任务详情"""
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

#### 6.1.3 工作流管理API

| 端点 | 方法 | 描述 | 参数 | 返回 |
|------|------|------|------|------|
| `/api/v1/workflows/{workflow_id}/state` | GET | 获取工作流当前状态 | `workflow_id`(必填): 工作流ID | 工作流状态 |
| `/api/v1/workflows/{workflow_id}/pause` | POST | 暂停工作流执行 | `workflow_id`(必填): 工作流ID | 操作结果 |
| `/api/v1/workflows/{workflow_id}/resume` | POST | 恢复工作流执行 | `workflow_id`(必填): 工作流ID | 操作结果 |
| `/api/v1/workflows/{workflow_id}/checkpoints` | GET | 获取工作流检查点列表 | `workflow_id`(必填): 工作流ID | 检查点列表 |
| `/api/v1/workflows/checkpoints/{checkpoint_id}/restore` | POST | 从检查点恢复工作流 | `checkpoint_id`(必填): 检查点ID | 恢复后的工作流状态 |

**示例实现**:
```python
@router.post("/workflows/{workflow_id}/pause", response_model=OperationResponse)
async def pause_workflow(workflow_id: str, workflow_service: WorkflowService = Depends(get_workflow_service)):
    """暂停工作流执行"""
    success = await workflow_service.pause_workflow(workflow_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to pause workflow")
    return {"success": True, "message": "Workflow paused successfully"}
```

#### 6.1.4 调度器API

| 端点 | 方法 | 描述 | 参数 | 返回 |
|------|------|------|------|------|
| `/api/v1/scheduler/status` | GET | 获取调度器状态 | 无 | 调度器状态信息 |
| `/api/v1/scheduler/steps/schedule` | POST | 调度步骤执行 | `step_ids`(必填): 步骤ID列表<br>`priority`(选填): 优先级 | 调度结果 |
| `/api/v1/scheduler/resources` | GET | 获取资源使用情况 | 无 | 资源使用统计 |

**示例实现**:
```python
@router.post("/scheduler/steps/schedule", response_model=ScheduleResponse)
async def schedule_steps(request: ScheduleRequest, scheduler: TaskScheduler = Depends(get_scheduler)):
    """调度步骤执行"""
    schedule_ids = await scheduler.schedule_steps(request.step_ids, request.priority)
    return {"schedule_ids": schedule_ids, "status": "SCHEDULED"}
```

### 6.2 外部集成接口

系统提供以下接口用于与外部系统集成：

#### 6.2.1 Dify API 集成接口

**接口定义**:
```python
class DifyService:
    """Dify API 集成服务"""
    
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
    
    async def get_knowledge(self, query: str) -> List[Dict]:
        """获取与查询相关的知识库内容"""
        endpoint = f"{self.base_url}/knowledge/search"
        response = await self.session.post(endpoint, json={"query": query})
        response.raise_for_status()
        return response.json()["data"]
```

#### 6.2.2 爬虫服务接口

**接口定义**:
```python
class WebCrawlerService:
    """网页爬虫服务"""
    
    async def crawl_url(self, url: str) -> Dict:
        """爬取指定URL的内容"""
        # 实现爬取逻辑
        
    async def search_and_crawl(self, keyword: str, limit: int = 5) -> List[Dict]:
        """搜索关键词并爬取结果"""
        # 实现搜索和爬取逻辑
```

#### 6.2.3 行业标准服务接口

**接口定义**:
```python
class IndustryStandardService:
    """行业标准服务"""
    
    async def get_standards_by_industry(self, industry_type: str) -> List[Dict]:
        """根据行业类型获取相关标准"""
        # 实现标准查询逻辑
        
    async def get_standard_details(self, standard_id: str) -> Dict:
        """获取标准详情"""
        # 实现标准详情查询逻辑
        
    async def search_standards(self, keywords: str) -> List[Dict]:
        """按关键词搜索标准"""
        # 实现标准搜索逻辑
```

#### 6.2.4 LangGraph 集成接口

**接口定义**:
```python
def build_task_graph() -> StateGraph:
    """构建任务管理工作流图"""
    builder = StateGraph(TaskState)
    
    # 添加节点
    builder.add_node("context_analyzer", context_analyzer_node)
    builder.add_node("objective_decomposer", objective_decomposer_node)
    builder.add_node("task_analyzer", task_analyzer_node)
    # ...其他节点
    
    # 添加边
    builder.add_edge("context_analyzer", "objective_decomposer")
    builder.add_edge("objective_decomposer", "task_analyzer")
    # ...其他边
    
    # 添加条件边
    builder.add_conditional_edges(
        "quality_evaluator",
        evaluate_quality,
        {
            "pass": "next_step",
            "fail": "retry_step"
        }
    )
    
    return builder.compile()
```

## 7. 集成方案

### 7.1 与现有DeerFlow系统集成

任务调度与目标管理系统将作为DeerFlow的扩展应用，保持与现有框架的兼容性并不影响现有流程。集成方案如下：

#### 7.1.1 代码级集成

**集成原则**：
- 保持独立模块化设计，避免直接修改现有DeerFlow核心代码
- 使用与DeerFlow一致的接口规范和代码风格
- 遵循DeerFlow的日志、配置和错误处理机制

**集成方式**：
```python
# 在DeerFlow主文件中加载任务系统（不修改现有代码）
from src.taskflow import register_taskflow

# 在应用启动时初始化任务系统
def initialize_application():
    # 初始化DeerFlow核心组件
    initialize_core_components()
    
    # 初始化任务调度系统（作为独立模块）
    register_taskflow()
```

#### 7.1.2 状态共享机制

**集成原则**：
- 使用DeerFlow的状态管理机制，确保状态一致性
- 扩展状态对象而非修改现有结构
- 提供明确的状态转换和映射机制

**集成方式**：
```python
# 扩展DeerFlow状态类，添加任务系统相关状态
class TaskflowState(MessagesState):
    """扩展DeerFlow状态，增加任务管理相关字段"""
    
    # 保留DeerFlow原有状态字段
    locale: str = "en-US"
    observations: list[str] = []
    current_plan: Plan | str = None
    
    # 添加任务系统相关字段
    objective_id: Optional[str] = None
    current_task: Optional[Dict[str, Any]] = None
    tasks: List[Dict[str, Any]] = []
```

#### 7.1.3 工作流集成

**集成原则**：
- 保持独立的工作流图定义
- 提供标准接口与DeerFlow工作流交互
- 使用相同的LangGraph工作流引擎

**集成方式**：
```python
# 定义任务系统工作流
taskflow_graph = build_task_graph()

# 在DeerFlow工作流中添加连接点
def build_integrated_graph():
    # 创建DeerFlow主工作流
    main_graph = build_graph()
    
    # 添加任务系统接入点
    main_graph.add_node("task_management", task_management_node)
    
    # 添加条件边
    main_graph.add_conditional_edges(
        "coordinator", 
        check_task_request,
        {
            "task_request": "task_management",
            "default": "planner"
        }
    )
    
    return main_graph
```

### 7.2 扩展点与插件机制

为确保系统的可扩展性，我们将实现标准化的扩展点和插件机制：

#### 7.2.1 智能体扩展机制

**设计原则**：
- 提供统一的智能体接口
- 支持动态注册和加载智能体
- 允许自定义处理逻辑和提示词

**实现方式**：
```python
# 智能体注册表
agent_registry = {}

def register_agent(agent_type: str, agent_class: Type[BaseAgent]):
    """注册智能体"""
    agent_registry[agent_type] = agent_class

def get_agent(agent_type: str, config: Dict[str, Any] = None) -> BaseAgent:
    """获取智能体实例"""
    if agent_type not in agent_registry:
        raise ValueError(f"Unknown agent type: {agent_type}")
    
    agent_class = agent_registry[agent_type]
    return agent_class(config or {})
```

#### 7.2.2 服务扩展机制

**设计原则**：
- 使用依赖注入模式
- 提供服务接口和抽象基类
- 支持服务替换和扩展

**实现方式**：
```python
# 服务注册和依赖注入
class ServiceContainer:
    """服务容器，管理所有服务实例"""
    
    def __init__(self):
        self.services = {}
        
    def register(self, service_type: str, instance: Any):
        """注册服务实例"""
        self.services[service_type] = instance
        
    def get(self, service_type: str) -> Any:
        """获取服务实例"""
        if service_type not in self.services:
            raise ValueError(f"Service not registered: {service_type}")
        return self.services[service_type]

# 全局服务容器
service_container = ServiceContainer()

# 依赖注入工厂函数
def get_db_service():
    return service_container.get("db_service")

def get_scheduler():
    return service_container.get("scheduler")
```

#### 7.2.3 工作流扩展机制

**设计原则**：
- 支持自定义节点和条件函数
- 允许动态修改工作流图
- 提供工作流组合机制

**实现方式**：
```python
# 动态工作流构建
class WorkflowBuilder:
    """工作流构建器，支持动态添加节点和边"""
    
    def __init__(self, state_type: Type):
        self.graph = StateGraph(state_type)
        self.nodes = {}
        self.conditional_routers = {}
        
    def add_node(self, name: str, node_function: Callable):
        """添加节点"""
        self.nodes[name] = node_function
        self.graph.add_node(name, node_function)
        return self
        
    def add_edge(self, source: str, target: str):
        """添加边"""
        self.graph.add_edge(source, target)
        return self
        
    def add_conditional_edges(self, source: str, router: Callable, targets: Dict[str, str]):
        """添加条件边"""
        self.conditional_routers[source] = router
        self.graph.add_conditional_edges(source, router, targets)
        return self
        
    def build(self):
        """构建工作流图"""
        return self.graph.compile()
```

## 8. 测试策略

### 8.1 单元测试

**测试目标**：验证各个组件的独立功能正确性

**测试范围**：
- 智能体单元测试
- 服务单元测试
- 工具函数单元测试
- 状态管理单元测试

**测试方法**：
- 使用 pytest 框架
- 使用 mock 对外部依赖进行模拟
- 使用参数化测试覆盖边界情况
- 针对主要类的所有公共方法编写测试

**示例测试**：
```python
def test_objective_decomposer_agent():
    """测试目标分解智能体"""
    # 准备测试数据
    test_state = {
        "query": "光伏组件出口法国需要完成哪些合规目标",
        "context_analysis": {
            "domain": "光伏行业",
            "scenario": "国际贸易合规"
        }
    }
    
    # 创建模拟LLM
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = json.dumps({
        "objectives": [
            {
                "objective_id": "obj-001",
                "title": "PPE2碳足迹要求分析"
            }
        ]
    })
    
    # 创建待测试的智能体
    agent = ObjectiveDecomposerAgent(llm=mock_llm)
    
    # 执行测试
    result = asyncio.run(agent(test_state))
    
    # 验证结果
    assert "objectives" in result
    assert len(result["objectives"]) >= 1
    assert result["objectives"][0]["title"] == "PPE2碳足迹要求分析"
```

### 8.2 集成测试

**测试目标**：验证多个组件协同工作的正确性

**测试范围**：
- 工作流集成测试
- API接口集成测试
- 数据库交互集成测试
- 外部服务集成测试

**测试方法**：
- 使用测试容器技术
- 构建端到端测试场景
- 使用测试数据库
- 模拟外部API响应

**示例测试**：
```python
def test_objective_creation_workflow():
    """测试目标创建和分解工作流"""
    # 配置测试环境
    config = {
        "db_url": "postgresql://test:test@localhost:5432/test_db",
        "enable_dify": False  # 禁用外部服务
    }
    
    # 初始化测试应用
    test_app = create_test_application(config)
    client = TestClient(test_app)
    
    # 执行测试
    response = client.post(
        "/api/v1/objectives",
        json={"query": "光伏组件出口法国需要完成哪些合规目标"}
    )
    
    # 验证响应
    assert response.status_code == 200
    objective_id = response.json()["objective_id"]
    
    # 等待工作流执行完成
    wait_for_workflow_completion(objective_id)
    
    # 验证工作流结果
    tasks_response = client.get(f"/api/v1/objectives/{objective_id}/tasks")
    tasks = tasks_response.json()
    
    assert len(tasks) > 0
    assert any("PPE2" in task["title"] for task in tasks)
```

### 8.3 性能测试

**测试目标**：验证系统在预期负载下的性能表现

**测试范围**：
- 高并发请求处理
- 资源使用效率
- 响应时间和吞吐量
- 长时间稳定性测试

**测试方法**：
- 使用 Locust 或 JMeter 进行负载测试
- 监控系统资源使用情况
- 分析性能瓶颈
- 进行长时间稳定性测试

**性能目标**：
- API响应时间 < 200ms（不含AI处理时间）
- 任务调度延迟 < 500ms
- 支持 50+ 个并发任务执行
- 内存泄漏为零
- 系统稳定运行时间 > 7天

## 9. 部署与维护

### 9.1 部署步骤

**部署环境准备**：
1. 安装Docker和Docker Compose
2. 安装PostgreSQL数据库
3. 配置环境变量和配置文件
4. 准备LLM API密钥和Dify API密钥

**容器化部署**：
```yaml
# docker-compose.yml
version: '3.8'

services:
  taskflow:
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/deerflow
      - DIFY_API_KEY=${DIFY_API_KEY}
      - LLM_API_KEY=${LLM_API_KEY}
    depends_on:
      - db
      
  db:
    image: postgres:15
    restart: always
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=deerflow
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

**部署流程**：
1. 克隆代码库
2. 配置环境变量
3. 执行数据库迁移
4. 启动Docker容器
5. 验证API访问和系统状态

### 9.2 监控与日志

**监控机制**：
- 使用Prometheus收集性能指标
- 使用Grafana构建监控仪表板
- 设置关键指标告警
- 定期生成系统健康报告

**监控指标**：
- API请求成功/失败率
- 任务调度延迟和完成率
- LLM API调用次数和延迟
- 资源使用情况（CPU/内存/磁盘）
- 活跃任务和目标数量

**日志策略**：
- 使用结构化日志格式
- 按组件和级别分类日志
- 实现日志轮转和归档
- 集成ELK或类似日志分析系统

**日志配置示例**：
```python
# logging_config.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'json',
            'filename': 'logs/taskflow.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10
        }
    },
    'loggers': {
        'src.taskflow': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        }
    }
}
```

### 9.3 维护计划

**定期维护任务**：
- 每日：检查系统状态和错误日志
- 每周：分析性能数据和资源使用情况
- 每月：进行数据库优化和备份验证
- 每季：进行系统安全审查和依赖更新

**备份策略**：
- 数据库每日增量备份
- 每周一次完整备份
- 备份数据加密存储
- 定期测试备份恢复

**更新流程**：
1. 在测试环境部署更新
2. 运行全面的测试套件
3. 执行性能测试比较
4. 准备回滚计划
5. 在维护窗口部署更新
6. 验证系统功能和性能
7. 监控系统稳定性

## 10. 时间线与里程碑

### 10.1 项目时间线

**总体时间表**：
- 开发准备阶段：1周
- 核心开发阶段：10周
- 测试和优化阶段：2周
- 部署和文档阶段：1周
- 总计：14周

**详细时间线**：
- 第1-2周：基础设施和数据模型开发
- 第3-5周：多智能体系统实现
- 第6-8周：任务调度与管理系统开发
- 第9-10周：API与集成接口开发
- 第11-12周：测试与优化
- 第13-14周：部署与文档完善

### 10.2 关键里程碑

**里程碑1：基础架构完成**（第2周末）
- 数据模型设计和实现完成
- 基础工具和配置模块完成
- 项目骨架搭建完成
- 验收标准：通过所有基础架构单元测试

**里程碑2：智能体系统实现**（第5周末）
- 所有专用智能体实现完成
- 提示词模板完成
- 智能体协作机制实现
- 验收标准：智能体测试覆盖率 > 85%

**里程碑3：调度系统完成**（第8周末）
- 任务调度器完成
- 工作流引擎集成完成
- 验收标准：能够正确调度和执行基本任务流程

**里程碑4：API完成**（第10周末）
- 所有API接口实现完成
- 外部服务集成完成
- 验收标准：API测试通过，能够通过API创建和管理研究目标

**里程碑5：测试完成**（第12周末）
- 所有功能和集成测试通过
- 性能测试达到目标
- 验收标准：所有测试通过，满足性能目标

**里程碑6：系统上线**（第14周末）
- 系统完成部署
- 文档和培训材料完成
- 验收标准：系统在生产环境稳定运行 