# DeerFlow技术框架分析

## 1. 项目概述

DeerFlow（Deep Exploration and Efficient Research Flow）是一个社区驱动的深度研究框架，旨在结合大语言模型（LLM）与专业工具（如网络搜索、网页爬取和Python代码执行等）来执行深度研究任务。项目采用多代理（Multi-Agent）系统架构，基于LangGraph框架构建，支持灵活的状态驱动工作流。

## 2. 技术栈

### 2.1 核心技术

- **语言与框架**：Python 3.12+, Node.js 22+
- **大语言模型集成**：通过LiteLLM支持多种LLM
- **工作流引擎**：LangGraph（基于状态图的工作流框架）
- **Web服务**：FastAPI + uvicorn
- **前端**：基于Node.js的Web UI
- **依赖管理**：uv（Python包管理）, pnpm（Node.js包管理）

### 2.2 第三方集成

- **搜索引擎**：
  - Tavily（默认，AI专用搜索API）
  - DuckDuckGo（隐私保护搜索引擎）
  - Brave Search（隐私保护+高级功能）
  - Arxiv（学术论文搜索）
- **文本转语音**：volcengine TTS API
- **其他工具**：
  - marp-cli（幻灯片生成）
  - LangSmith（追踪和监控）

## 3. 系统架构

DeerFlow采用模块化的多代理系统架构，基于LangGraph实现状态驱动的工作流。系统组件通过明确定义的消息传递系统进行通信。

![架构图示](../assets/architecture.png)

### 3.1 核心工作流程

1. **Coordinator**（协调器）：工作流生命周期管理
   - 作为用户和系统的主要接口
   - 基于用户输入启动研究过程
   - 根据需要将任务委派给Planner

2. **Planner**（规划器）：任务分解和规划
   - 分析研究目标并创建结构化执行计划
   - 确定是否有足够的上下文或需要更多研究
   - 管理研究流程并决定何时生成最终报告

3. **Research Team**（研究团队）：执行计划的专业代理集合
   - **Researcher**（研究员）：使用搜索引擎、爬虫工具等收集信息
   - **Coder**（程序员）：使用Python REPL工具处理代码分析、执行和技术任务

4. **Reporter**（报告员）：研究输出的最终处理阶段
   - 整合研究团队的发现
   - 处理和结构化收集的信息
   - 生成全面的研究报告

## 4. 核心模块详解

### 4.1 工作流引擎 (src/graph/)

项目使用LangGraph构建状态驱动的工作流，通过`StateGraph`定义代理节点和状态转换。

核心文件：
- `src/graph/builder.py`：构建状态图和工作流
- `src/graph/nodes.py`：定义各个节点（协调器、规划器、研究员等）的行为
- `src/graph/types.py`：定义状态和类型

关键的状态转换：
- 从Coordinator到Planner：初始查询处理与背景调查
- 从Planner到Human Feedback：计划审查与修改
- 从Human Feedback到Research Team：计划执行
- 从Research Team到Researcher/Coder：根据任务类型分配
- 从执行完成到Reporter：汇总研究结果并生成报告

### 4.2 代理系统 (src/agents/)

DeerFlow使用LangGraph的预构建ReAct代理，根据不同任务配置不同工具：

- **Researcher代理**：配备`web_search_tool`和`crawl_tool`
- **Coder代理**：配备`python_repl_tool`

代理创建采用工厂模式，确保一致的配置，并通过prompt模板定义代理行为。

### 4.3 工具集成 (src/tools/)

项目集成了多种工具，扩展代理能力：

- **搜索工具**：支持多种搜索引擎，通过配置文件动态选择
  - `tavily_search_tool`
  - `duckduckgo_search_tool`
  - `brave_search_tool`
  - `arxiv_search_tool`
- **爬虫工具**：`crawl_tool`用于网页内容提取
- **代码执行**：`python_repl_tool`用于Python代码分析和执行
- **文本转语音**：`VolcengineTTS`用于生成音频报告

### 4.4 API服务 (src/server/)

FastAPI实现的API服务，提供以下端点：

- `/api/chat/stream`：流式处理聊天请求
- `/api/tts`：文本转语音服务
- `/api/podcast/generate`：生成播客内容
- `/api/ppt/generate`：生成演示文稿
- `/api/prose/generate`：生成散文内容
- `/api/mcp/server/metadata`：MCP服务器元数据

### 4.5 内容生成 (src/podcast/, src/ppt/, src/prose/)

提供额外的内容生成功能：
- 播客生成（带音频合成）
- 简单PowerPoint演示文稿创建
- 增强文本内容生成

## 5. 状态管理与交互

### 5.1 状态定义

项目通过`State`类扩展LangGraph的`MessagesState`，添加了额外字段：
- `locale`：用户语言区域
- `observations`：观察结果列表
- `plan_iterations`：计划迭代计数
- `current_plan`：当前执行计划
- `final_report`：最终报告内容
- `auto_accepted_plan`：是否自动接受计划
- `enable_background_investigation`：是否启用背景调查
- `background_investigation_results`：背景调查结果

### 5.2 人机协作

项目支持"Human-in-the-loop"机制：
1. 用户可以审查生成的研究计划
2. 接受计划（回复`[ACCEPTED]`）或提供修改建议（`[EDIT PLAN]...`）
3. 系统整合反馈并生成修订计划

### 5.3 MCP集成

DeerFlow支持Model Context Protocol (MCP)服务集成：
1. 在工作流配置中定义MCP服务器
2. 动态将MCP工具添加到适当的代理（如研究员或程序员）
3. 通过统一接口调用外部服务

## 6. 执行流程示例

以下是DeerFlow处理用户查询的典型流程：

1. **用户输入**：提交研究问题（如"如何在医疗保健中采用AI？"）
2. **协调器处理**：分析查询，确定需要深度研究，触发背景调查
3. **背景调查**：使用配置的搜索引擎收集初步信息
4. **计划生成**：规划器根据查询和背景信息创建研究计划，分为多个步骤
5. **人机交互**：用户审查并批准（或修改）计划
6. **研究执行**：
   - 研究团队按计划顺序执行步骤
   - 研究员使用搜索工具收集信息
   - 程序员使用Python REPL分析数据或执行代码
7. **报告生成**：收集所有研究结果，生成结构化报告
8. **可选扩展**：生成播客、演示文稿或其他衍生内容

## 7. 部署与扩展

### 7.1 部署选项

- **本地控制台UI**：基本交互界面
- **Web UI**：更动态的交互体验
- **Docker部署**：容器化部署，支持后端和前端
- **Docker Compose**：单命令启动完整环境

### 7.2 扩展机制

DeerFlow设计为可扩展的：
- 添加新的搜索引擎或工具
- 集成额外的MCP服务
- 扩展内容生成能力（如新的演示格式）
- 自定义代理行为和工作流程

## 8. 总结

DeerFlow是一个功能强大的深度研究框架，结合了最先进的LLM技术与专业工具，实现自动化深度研究。其模块化、多代理架构提供了高度的灵活性和扩展性，同时支持人机协作，确保研究结果的质量和相关性。该框架适用于广泛的应用场景，从学术研究到商业分析，展示了AI辅助研究的强大潜力。 