# 上下文
文件名：taskflow_implementation_plan.md
创建于：2025-05-19
创建者：AI
关联协议：RIPER-5 + Multidimensional + Agent Protocol 

# 任务描述
根据DeerFlow任务调度与目标管理系统开发计划文档，分步实现整个系统。数据库连接已更新到.env文件中，需要在jdbc.url的基础上进行开发。

# 项目概述
DeerFlow任务调度与目标管理系统是基于DeerFlow框架的扩展应用，旨在实现复杂研究目标的分解、任务调度和多智能体协作。该系统将支持结构化目标分解、自动任务调度和智能体协作，并提供RESTful API接口以便与其他系统集成。

---
*以下部分由 AI 在协议执行过程中维护*
---

# 分析 (由 RESEARCH 模式填充)
## 当前项目状态
- 项目是基于Python的DeerFlow框架
- 使用了LangGraph作为工作流引擎
- 已有配置文件conf.yaml，主要包含LLM配置
- 数据库连接信息在.env文件中，使用jdbc连接MySQL数据库
- 项目依赖没有明确包含SQLAlchemy，需要添加

## 项目结构
项目当前组织结构如下：
- src/: 主要源代码
  - prompts/: 提示词模板
  - utils/: 工具函数
  - llms/: LLM客户端
  - agents/: 智能体定义
  - config/: 配置管理
  - graph/: 工作流图
  - server/: 服务器相关
  - workflow.py: 工作流定义

## 要实现的内容
根据开发计划文档，我们需要创建以下新模块和功能：
1. 数据库模型和服务
   - 创建任务、目标、步骤等数据模型
   - 实现数据库操作服务
   - 配置ORM映射

2. 智能体系统
   - 基础智能体抽象类
   - 各种专用智能体实现
   - 智能体提示词模板

3. 工作流图系统
   - 工作流图构建器
   - 工作流节点定义
   - 条件路由实现

4. 任务调度系统
   - 任务分发器
   - 优先级管理
   - 任务队列实现
   - 工作线程池

5. API接口
   - FastAPI应用
   - RESTful端点
   - 请求/响应模型

# 提议的解决方案 (由 INNOVATE 模式填充)

## 1. 系统架构设计

我们将采用模块化、面向服务的架构，以确保系统各组件之间的低耦合和高内聚。系统架构如下：

### 1.1 分层架构

```
                       +----------------+
                       |     Client     |
                       +-------+--------+
                               |
                               v
+----------------+     +-------+--------+
|   External     |<--->|      API       |
|   Services     |     +-------+--------+
+----------------+             |
                               v
               +---------------+---------------+
               |                               |
       +-------v--------+             +--------v-------+
       |   Workflow     |<----------->|    Scheduler   |
       |    Engine      |             |    System      |
       +-------+--------+             +--------+-------+
               |                               |
               v                               v
       +-------+--------+             +--------+-------+
       |    Agents      |<----------->|     Task       |
       |    System      |             |    Queue       |
       +-------+--------+             +----------------+
               |
               v
       +-------+--------+
       |   Database     |
       |    Service     |
       +----------------+
```

### 1.2 主要组件和技术选择

1. **数据库服务**
   - 使用SQLAlchemy ORM与MySQL数据库交互
   - 实现数据模型和数据访问服务
   - 支持异步操作，提高系统响应性能

2. **智能体系统**
   - 基于提示工程的智能体实现
   - 统一的智能体接口设计
   - 与LangGraph工作流无缝集成

3. **工作流图系统**
   - 使用LangGraph构建工作流图
   - 状态驱动的节点和边
   - 支持条件路由和分支执行

4. **任务调度系统**
   - 基于优先级的任务队列
   - 异步任务执行器
   - 资源监控和负载均衡

5. **API接口**
   - 使用FastAPI构建RESTful API
   - 支持WebSocket实时更新
   - 标准化错误处理和响应格式

## 2. 实现策略

### 2.1 数据库模型设计

我们将使用面向对象的方式定义数据模型，采用SQLAlchemy的声明式ORM风格：

```python
# 简化的模型示例
class Objective(Base):
    __tablename__ = "objectives"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    tasks = relationship("Task", back_populates="objective", cascade="all, delete-orphan")
```

### 2.2 智能体系统实现

我们将采用以下模式实现智能体：

1. **基础智能体抽象类** - 提供共通功能和接口
2. **专用智能体类** - 实现特定领域功能
3. **提示词模板** - 通过模板分离提示词内容和逻辑

```python
# 简化的智能体示例
class BaseAgent:
    def __init__(self, llm):
        self.llm = llm
        
    async def __call__(self, state):
        """处理状态并返回更新后的状态"""
        # 预处理
        formatted_input = self._format_input(state)
        
        # 调用LLM
        response = await self.llm.invoke(formatted_input)
        
        # 后处理
        result = self._process_response(response)
        
        # 更新状态
        return self._update_state(state, result)
```

### 2.3 工作流系统实现

我们将使用LangGraph构建工作流图，每个节点对应一个智能体或处理函数：

```python
# 简化的工作流示例
def build_objective_workflow():
    builder = StateGraph(WorkflowState)
    
    # 添加节点
    builder.add_node("context_analysis", context_analysis_node)
    builder.add_node("objective_decomposition", objective_decomposition_node)
    builder.add_node("task_analysis", task_analysis_node)
    
    # 添加边
    builder.add_edge("context_analysis", "objective_decomposition")
    builder.add_edge("objective_decomposition", "task_analysis")
    
    # 添加条件边
    builder.add_conditional_edges(
        "task_analysis",
        route_tasks,
        {
            "research_task": "research_node",
            "processing_task": "processing_node",
            "default": "END"
        }
    )
    
    return builder.compile()
```

### 2.4 任务调度系统实现

我们将实现基于优先级的任务队列和异步执行器：

```python
# 简化的调度器示例
class TaskScheduler:
    def __init__(self, max_workers=10):
        self.task_queue = PriorityQueue()
        self.workers = [Worker(self.task_queue) for _ in range(max_workers)]
        self.running = False
        
    async def start(self):
        """启动调度器"""
        self.running = True
        worker_tasks = [worker.start() for worker in self.workers]
        await asyncio.gather(*worker_tasks)
        
    async def schedule(self, task, priority=0):
        """将任务添加到队列"""
        await self.task_queue.put((priority, task))
        return task.id
```

### 2.5 API接口实现

使用FastAPI实现RESTful API接口：

```python
# 简化的API示例
app = FastAPI(title="DeerFlow Task API")

@app.post("/api/v1/objectives", response_model=ObjectiveResponse)
async def create_objective(objective: ObjectiveCreate, db: Database = Depends(get_db)):
    """创建新的研究目标"""
    objective_id = await db.create_objective({
        "title": objective.query,
        "description": objective.description,
        "status": "CREATED"
    })
    
    # 启动工作流
    asyncio.create_task(start_objective_workflow(objective_id, objective.query))
    
    return {"objective_id": objective_id, "status": "CREATED"}
```

## 3. 迁移和集成策略

为了与现有DeerFlow系统集成，我们将采用以下策略：

1. 保持独立模块化设计，避免修改DeerFlow核心代码
2. 通过注册机制在DeerFlow启动时初始化taskflow模块
3. 扩展DeerFlow状态对象以支持任务管理功能
4. 提供明确的接口与DeerFlow工作流交互

## 4. 开发计划

我们将按照以下顺序开发各个组件：

1. **初始设置和目录结构**
   - 创建taskflow包和子包结构
   - 设置基本工具和配置

2. **数据库模型和服务**
   - 定义数据模型
   - 实现数据库服务
   - 创建数据库迁移脚本

3. **智能体系统**
   - 实现BaseAgent基类
   - 开发各种专用智能体
   - 创建提示词模板

4. **工作流图系统**
   - 实现工作流构建器
   - 定义工作流节点和路由
   - 创建工作流状态类型

5. **任务调度系统**
   - 实现任务队列和优先级管理
   - 开发工作线程池和资源管理
   - 实现任务分发和监控

6. **API接口**
   - 实现RESTful端点
   - 开发请求/响应模型
   - 集成错误处理和文档

7. **集成和测试**
   - 将taskflow与DeerFlow集成
   - 编写单元测试和集成测试
   - 进行性能测试和优化 