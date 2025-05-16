

# DeerFlow任务调度与目标管理系统设计文档

## 1. 系统概述

本系统是基于DeerFlow框架的扩展应用，旨在实现一个能够管理和调度复杂研究任务的AI辅助系统。当用户提交研究问题（如"光伏组件出口法国需要完成哪些合规目标"）时，系统将自动分解为任务目标和步骤，并通过调度机制保证各个目标和步骤能够被正确、完整地执行。

## 2. 系统架构

系统采用混合架构设计，由以下几个主要部分组成：

### 2.1 核心组件

1. **任务管理服务（Task Management Service）**
   - 负责任务的创建、分解、调度和状态管理
   - 提供任务的持久化存储和状态跟踪
   - 实现任务超时检测和重试机制

2. **DeerFlow研究框架（扩展）**
   - 基于现有DeerFlow框架
   - 添加新的节点以支持任务分解和管理
   - 扩展State对象以包含任务相关信息

3. **数据库服务（Database Service）**
   - 存储任务、目标和步骤信息
   - 记录执行状态和结果
   - 支持任务恢复和历史查询

4. **Dify API集成服务**
   - 封装与Dify API的交互
   - 处理知识库检索和相关内容获取

5. **爬虫服务（Web Crawler Service）**
   - 按需获取补充信息
   - 支持特定领域的数据爬取

### 2.2 架构图

```
+-------------------+     +---------------------+     +-------------------+
|                   |     |                     |     |                   |
|    客户端/用户    +---->+  DeerFlow Web API   +---->+  任务管理服务    |
|                   |     |                     |     |                   |
+-------------------+     +---------------------+     +--------+----------+
                                                              |
                                                              v
+-------------------+     +---------------------+     +-------------------+
|                   |     |                     |     |                   |
|   爬虫服务        |<----+  扩展DeerFlow框架   |<----+   数据库服务     |
|                   |     |                     |     |                   |
+-------------------+     +---------------------+     +-------------------+
                                    ^
                                    |
                          +---------+---------+
                          |                   |
                          |   Dify API服务    |
                          |                   |
                          +-------------------+
```

## 3. 详细设计

### 3.1 数据模型设计

#### 3.1.1 数据库模型

1. **Task（任务）表**
   ```sql
   CREATE TABLE tasks (
       task_id UUID PRIMARY KEY,
       title TEXT NOT NULL,
       description TEXT,
       status TEXT NOT NULL, -- CREATED, IN_PROGRESS, COMPLETED, FAILED
       created_at TIMESTAMP NOT NULL,
       updated_at TIMESTAMP NOT NULL,
       completed_at TIMESTAMP,
       retry_count INTEGER DEFAULT 0,
       max_retries INTEGER DEFAULT 3
   );
   ```

2. **Goal（目标）表**
   ```sql
   CREATE TABLE goals (
       goal_id UUID PRIMARY KEY,
       task_id UUID REFERENCES tasks(task_id),
       title TEXT NOT NULL,
       description TEXT,
       status TEXT NOT NULL, -- PENDING, IN_PROGRESS, COMPLETED, FAILED
       priority INTEGER DEFAULT 0,
       created_at TIMESTAMP NOT NULL,
       updated_at TIMESTAMP NOT NULL,
       completed_at TIMESTAMP,
       is_sufficient BOOLEAN DEFAULT FALSE,
       evaluation_criteria TEXT,
       retry_count INTEGER DEFAULT 0,
       max_retries INTEGER DEFAULT 3
   );
   ```

3. **Step（步骤）表**
   ```sql
   CREATE TABLE steps (
       step_id UUID PRIMARY KEY,
       goal_id UUID REFERENCES goals(goal_id),
       title TEXT NOT NULL,
       description TEXT,
       status TEXT NOT NULL, -- PENDING, IN_PROGRESS, COMPLETED, FAILED
       priority INTEGER DEFAULT 0,
       created_at TIMESTAMP NOT NULL,
       updated_at TIMESTAMP NOT NULL,
       completed_at TIMESTAMP,
       is_sufficient BOOLEAN DEFAULT FALSE,
       evaluation_criteria TEXT,
       retry_count INTEGER DEFAULT 0,
       max_retries INTEGER DEFAULT 3,
       timeout_seconds INTEGER DEFAULT 300
   );
   ```

4. **Content（内容）表**
   ```sql
   CREATE TABLE contents (
       content_id UUID PRIMARY KEY,
       reference_id UUID NOT NULL, -- 关联到goal_id或step_id
       reference_type TEXT NOT NULL, -- 'GOAL'或'STEP'
       content_type TEXT NOT NULL, -- 'DIFY_KNOWLEDGE', 'CRAWLED_DATA', 'AGENT_RESULT'
       content TEXT,
       metadata JSONB,
       created_at TIMESTAMP NOT NULL
   );
   ```

5. **Schedule（调度）表**
   ```sql
   CREATE TABLE schedules (
       schedule_id UUID PRIMARY KEY,
       reference_id UUID NOT NULL, -- 关联到task_id, goal_id或step_id
       reference_type TEXT NOT NULL, -- 'TASK', 'GOAL'或'STEP'
       status TEXT NOT NULL, -- SCHEDULED, RUNNING, COMPLETED, FAILED
       scheduled_at TIMESTAMP NOT NULL,
       started_at TIMESTAMP,
       completed_at TIMESTAMP,
       retry_count INTEGER DEFAULT 0,
       error_message TEXT
   );
   ```

#### 3.1.2 对象模型设计

```python
# 任务状态枚举
class TaskStatus(str, Enum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# 目标/步骤状态枚举
class WorkStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# 内容类型枚举
class ContentType(str, Enum):
    DIFY_KNOWLEDGE = "DIFY_KNOWLEDGE"
    CRAWLED_DATA = "CRAWLED_DATA"
    AGENT_RESULT = "AGENT_RESULT"

# 任务模型
class Task(BaseModel):
    task_id: UUID
    title: str
    description: Optional[str] = None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    
# 目标模型
class Goal(BaseModel):
    goal_id: UUID
    task_id: UUID
    title: str
    description: Optional[str] = None
    status: WorkStatus
    priority: int = 0
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    is_sufficient: bool = False
    evaluation_criteria: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

# 步骤模型
class Step(BaseModel):
    step_id: UUID
    goal_id: UUID
    title: str
    description: Optional[str] = None
    status: WorkStatus
    priority: int = 0
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    is_sufficient: bool = False
    evaluation_criteria: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
```

### 3.2 扩展DeerFlow框架

#### 3.2.1 新增节点

1. **Task Decomposer节点（Agent1）**
   - 功能：分析用户问题，分解为一级任务目标
   - 输入：用户查询、Dify知识库内容
   - 输出：任务目标列表

2. **Goal Analyzer节点（Agent2）**
   - 功能：分析每个一级任务目标，分解为具体步骤
   - 输入：任务目标、相关Dify知识库内容
   - 输出：步骤列表

3. **Sufficiency Evaluator节点**
   - 功能：评估目标/步骤的内容是否足够，是否需要爬虫
   - 输入：目标/步骤内容
   - 输出：是否足够的判断结果及理由

4. **Completion Evaluator节点**
   - 功能：评估目标/步骤是否完成，完成质量如何
   - 输入：目标/步骤内容、评估标准
   - 输出：评估结果和分数

#### 3.2.2 扩展State类型

```python
class EnhancedState(State):
    """扩展DeerFlow的State类，添加任务管理相关字段。"""
    
    # 任务相关
    current_task_id: Optional[UUID] = None
    current_task_title: Optional[str] = None
    
    # 目标相关
    current_goal_id: Optional[UUID] = None
    current_goal_title: Optional[str] = None
    goals: List[Dict] = []
    
    # 步骤相关
    current_step_id: Optional[UUID] = None
    current_step_title: Optional[str] = None
    steps: List[Dict] = []
    
    # 评估相关
    evaluation_result: Optional[Dict] = None
    content_sufficient: Optional[bool] = None
```

### 3.3 任务管理服务设计

#### 3.3.1 主要组件

1. **TaskManager类**
   - 负责创建、更新和管理任务
   - 与数据库交互保存任务状态
   - 提供任务查询和状态更新接口

2. **TaskDecomposer类**
   - 调用DeerFlow框架分解任务
   - 创建并保存目标到数据库

3. **GoalAnalyzer类**
   - 分析目标，生成步骤
   - 保存步骤到数据库

4. **Scheduler类**
   - 管理任务、目标和步骤的调度
   - 检测超时和失败情况
   - 实现重试机制

5. **EvaluationService类**
   - 评估内容是否足够
   - 评估目标/步骤是否完成

#### 3.3.2 任务流程设计

```
1. 用户提交研究问题
2. 系统创建新Task记录
3. 系统调用Dify API获取相关知识库内容
4. Task Decomposer将任务分解为多个Goal
5. 对每个Goal：
   a. 系统获取Goal相关知识库内容
   b. Goal Analyzer将Goal分解为多个Step
   c. 保存Step到数据库
6. Scheduler开始调度各个Step：
   a. 获取Step内容
   b. 评估内容是否足够
   c. 如不足够，调用爬虫获取额外信息
   d. 执行Step
   e. 评估Step是否完成
   f. 如未完成且未超过重试次数，安排重试
7. 当所有Step完成，评估Goal是否完成
8. 当所有Goal完成，标记Task为完成
```

### 3.4 Dify API集成服务

#### 3.4.1 主要接口

1. **知识库检索接口**
   - 功能：根据查询获取相关知识库内容
   - 输入：查询文本
   - 输出：相关知识库内容列表

#### 3.4.2 实现类

```python
class DifyService:
    """Dify API集成服务类"""
    
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

### 3.5 爬虫服务设计

#### 3.5.1 主要接口

1. **通用网页爬取接口**
   - 功能：爬取指定URL的网页内容
   - 输入：URL
   - 输出：网页内容和元数据

2. **关键词搜索爬取接口**
   - 功能：搜索关键词并爬取相关网页
   - 输入：关键词、爬取数量限制
   - 输出：爬取内容列表

#### 3.5.2 实现类

```python
class WebCrawlerService:
    """网页爬虫服务类"""
    
    def __init__(self, proxy_config: Optional[Dict] = None):
        self.session = requests.Session()
        if proxy_config:
            self.session.proxies.update(proxy_config)
    
    async def crawl_url(self, url: str) -> Dict:
        """爬取指定URL的内容"""
        response = await self.session.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 提取正文内容
        content = self._extract_main_content(soup)
        
        return {
            "url": url,
            "title": soup.title.text if soup.title else "",
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
    
    async def search_and_crawl(self, keyword: str, limit: int = 5) -> List[Dict]:
        """搜索关键词并爬取结果"""
        # 使用搜索引擎API或爬取搜索结果页面
        search_results = await self._search(keyword, limit)
        
        # 爬取搜索结果中的URL
        crawled_results = []
        for result in search_results:
            try:
                content = await self.crawl_url(result["url"])
                crawled_results.append(content)
            except Exception as e:
                logger.error(f"Error crawling {result['url']}: {str(e)}")
        
        return crawled_results
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """从网页提取主要内容"""
        # 实现内容提取逻辑
        # 可以使用启发式规则或NLP模型分析
        pass
    
    async def _search(self, keyword: str, limit: int) -> List[Dict]:
        """实现搜索功能"""
        # 可以使用搜索引擎API或爬取搜索结果页面
        pass
```

### 3.6 调度机制设计

#### 3.6.1 调度器实现

```python
class TaskScheduler:
    """任务调度器类"""
    
    def __init__(self, db_service, check_interval: int = 30):
        self.db_service = db_service
        self.check_interval = check_interval
        self.running = False
        self.scheduler_thread = None
    
    def start(self):
        """启动调度器"""
        if self.running:
            return
            
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
    
    def stop(self):
        """停止调度器"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=10)
    
    def _scheduler_loop(self):
        """调度器主循环"""
        while self.running:
            try:
                # 检查要执行的任务
                self._check_scheduled_tasks()
                
                # 检查超时的任务
                self._check_timeout_tasks()
                
                # 处理失败的任务
                self._handle_failed_tasks()
                
                # 更新任务状态
                self._update_task_statuses()
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                
            time.sleep(self.check_interval)
    
    def _check_scheduled_tasks(self):
        """检查并启动需要执行的任务"""
        # 获取所有状态为SCHEDULED且执行时间已到的任务
        scheduled_tasks = self.db_service.get_executable_schedules()
        
        for schedule in scheduled_tasks:
            try:
                # 更新状态为RUNNING
                self.db_service.update_schedule_status(
                    schedule["schedule_id"], 
                    "RUNNING", 
                    started_at=datetime.now()
                )
                
                # 启动任务执行
                threading.Thread(
                    target=self._execute_schedule,
                    args=(schedule,)
                ).start()
                
            except Exception as e:
                logger.error(f"Error starting schedule {schedule['schedule_id']}: {str(e)}")
                self.db_service.update_schedule_status(
                    schedule["schedule_id"],
                    "FAILED",
                    error_message=str(e)
                )
    
    def _check_timeout_tasks(self):
        """检查并处理超时任务"""
        # 获取所有正在运行但已超时的任务
        timeout_tasks = self.db_service.get_timeout_schedules()
        
        for schedule in timeout_tasks:
            try:
                # 标记为失败
                self.db_service.update_schedule_status(
                    schedule["schedule_id"],
                    "FAILED",
                    error_message="Task execution timeout"
                )
                
                # 安排重试
                self._schedule_retry(schedule)
                
            except Exception as e:
                logger.error(f"Error handling timeout for schedule {schedule['schedule_id']}: {str(e)}")
    
    def _handle_failed_tasks(self):
        """处理失败的任务"""
        # 获取所有失败的任务
        failed_tasks = self.db_service.get_failed_schedules()
        
        for schedule in failed_tasks:
            try:
                # 检查是否可以重试
                self._schedule_retry(schedule)
            except Exception as e:
                logger.error(f"Error handling failed schedule {schedule['schedule_id']}: {str(e)}")
    
    def _schedule_retry(self, schedule):
        """安排任务重试"""
        # 获取当前重试次数
        reference_type = schedule["reference_type"]
        reference_id = schedule["reference_id"]
        
        if reference_type == "TASK":
            retry_info = self.db_service.get_task(reference_id)
        elif reference_type == "GOAL":
            retry_info = self.db_service.get_goal(reference_id)
        elif reference_type == "STEP":
            retry_info = self.db_service.get_step(reference_id)
        else:
            logger.error(f"Unknown reference type: {reference_type}")
            return
        
        # 检查是否超过最大重试次数
        if retry_info["retry_count"] >= retry_info["max_retries"]:
            logger.info(f"{reference_type} {reference_id} exceeded max retries")
            return
        
        # 增加重试计数
        new_retry_count = retry_info["retry_count"] + 1
        
        # 更新重试计数
        if reference_type == "TASK":
            self.db_service.update_task(reference_id, {"retry_count": new_retry_count})
        elif reference_type == "GOAL":
            self.db_service.update_goal(reference_id, {"retry_count": new_retry_count})
        elif reference_type == "STEP":
            self.db_service.update_step(reference_id, {"retry_count": new_retry_count})
        
        # 创建新的调度
        retry_delay = min(30 * (2 ** new_retry_count), 3600)  # 指数退避，最大1小时
        self.db_service.create_schedule({
            "reference_id": reference_id,
            "reference_type": reference_type,
            "status": "SCHEDULED",
            "scheduled_at": datetime.now() + timedelta(seconds=retry_delay)
        })
    
    def _execute_schedule(self, schedule):
        """执行调度任务"""
        reference_type = schedule["reference_type"]
        reference_id = schedule["reference_id"]
        
        try:
            # 根据引用类型执行不同操作
            if reference_type == "TASK":
                self._execute_task(reference_id)
            elif reference_type == "GOAL":
                self._execute_goal(reference_id)
            elif reference_type == "STEP":
                self._execute_step(reference_id)
            else:
                raise ValueError(f"Unknown reference type: {reference_type}")
            
            # 更新为完成状态
            self.db_service.update_schedule_status(
                schedule["schedule_id"],
                "COMPLETED",
                completed_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error executing schedule {schedule['schedule_id']}: {str(e)}")
            self.db_service.update_schedule_status(
                schedule["schedule_id"],
                "FAILED",
                error_message=str(e)
            )
```

### 3.7 API接口设计

#### 3.7.1 REST API

1. **任务管理API**
   - `POST /api/tasks`：创建新任务
   - `GET /api/tasks/{task_id}`：获取任务详情
   - `GET /api/tasks/{task_id}/goals`：获取任务的目标列表
   - `GET /api/tasks/{task_id}/status`：获取任务状态

2. **目标管理API**
   - `GET /api/goals/{goal_id}`：获取目标详情
   - `GET /api/goals/{goal_id}/steps`：获取目标的步骤列表
   - `GET /api/goals/{goal_id}/status`：获取目标状态

3. **步骤管理API**
   - `GET /api/steps/{step_id}`：获取步骤详情
   - `GET /api/steps/{step_id}/status`：获取步骤状态
   - `GET /api/steps/{step_id}/content`：获取步骤内容

4. **调度管理API**
   - `POST /api/schedules/retry/{schedule_id}`：手动触发重试
   - `GET /api/schedules/task/{task_id}`：获取任务的调度历史

#### 3.7.2 WebSocket API

1. **实时状态更新**
   - `ws://server/api/ws/tasks/{task_id}`：订阅任务状态更新

## 4. 实现计划

### 4.1 实施阶段

1. **阶段一：基础设施和数据模型（第1-2周）**
   - 设置数据库和ORM
   - 实现数据模型和基本CRUD操作
   - 集成Dify API服务

2. **阶段二：核心服务实现（第3-4周）**
   - 实现任务管理服务
   - 实现调度器
   - 扩展DeerFlow框架

3. **阶段三：集成服务（第5-6周）**
   - 实现爬虫服务
   - 集成评估服务
   - 完成API接口

4. **阶段四：测试和优化（第7-8周）**
   - 单元测试和集成测试
   - 性能优化
   - 文档和部署指南

### 4.2 技术栈选择

1. **后端框架**
   - FastAPI（提供REST API和WebSocket支持）
   - Pydantic（数据验证和序列化）
   - SQLAlchemy（ORM和数据库交互）

2. **数据库**
   - PostgreSQL（主数据库，支持JSON和全文搜索）
   - Redis（缓存和任务队列）

3. **任务调度**
   - APScheduler（调度器框架）
   - Celery（分布式任务队列，可选）

4. **监控和日志**
   - Prometheus（监控指标收集）
   - ELK Stack（日志管理，可选）

5. **部署**
   - Docker（容器化）
   - Docker Compose（本地开发和测试）
   - Kubernetes（生产环境，可选）

## 5. 系统评估标准

### 5.1 性能指标

- 任务创建和分解时间：≤ 5秒
- 步骤执行平均时间：≤ 30秒
- 系统能够处理的并发任务数：≥ 50
- API响应时间：≤ 200ms（95%请求）
- 任务完成率：≥ 95%

### 5.2 质量指标

- 任务分解准确率：≥ 90%
- 内容充分性评估准确率：≥ 85%
- 目标完成评估准确率：≥ 90%
- 系统可用性：≥ 99.9%

## 6. 未来扩展

1. **多语言支持**
   - 扩展系统支持多语言查询和内容生成

2. **高级分析功能**
   - 任务执行数据分析和优化建议
   - 知识库内容质量评估和改进

3. **用户反馈机制**
   - 收集用户对任务结果的反馈
   - 基于反馈持续改进系统

4. **行业特定模块**
   - 针对特定行业（如法律、医疗、金融）的专业模块
   - 特定行业爬虫和数据提取规则

实施检查清单：
1. 创建数据库模型和ORM映射
2. 设计任务管理服务核心类
3. 实现Dify API集成服务类
4. 扩展DeerFlow框架，添加新节点
5. 实现爬虫服务
6. 构建任务调度机制
7. 开发评估服务组件
8. 创建API接口
