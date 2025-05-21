# TaskFlow LLM配置指南

本文档介绍了TaskFlow项目中LLM（大型语言模型）的配置和使用方法。TaskFlow现已采用与DeerFlow一致的LLM配置方式，提供了更简洁直观的配置和调用接口。

## 配置文件

TaskFlow使用YAML格式的配置文件来管理LLM设置。配置文件默认位于项目根目录下的`conf.taskflow.yaml`。

### 示例配置

项目根目录下的`conf.taskflow.yaml.example`文件提供了一个完整的配置示例：

```yaml
# 基础模型配置 - 用于一般任务
BASIC_MODEL:
  model: "gpt-3.5-turbo-1106"
  temperature: 0.0
  max_tokens: 4000
  api_key: "${OPENAI_API_KEY}"  # 从环境变量获取，或直接填写
  base_url: "${OPENAI_API_BASE}"  # 可选，用于自定义API端点

# 推理模型配置 - 用于需要深度推理的任务
REASONING_MODEL:
  model: "gpt-4-turbo-preview"
  temperature: 0.1
  max_tokens: 8000
  # ... 其他配置
```

### 配置项说明

每个模型配置包含以下常用选项：

| 配置项 | 说明 | 示例值 |
| ----- | ---- | ----- |
| model | 模型名称 | "gpt-4" |
| temperature | 生成温度 | 0.0 |
| max_tokens | 最大令牌数 | 4000 |
| api_key | API密钥 | "${OPENAI_API_KEY}" |
| base_url | API基础URL | "https://api.openai.com/v1" |

可以使用`${ENV_VAR}`语法从环境变量中获取敏感信息，如API密钥。

## LLM类型

TaskFlow定义了以下几种LLM类型，用于不同的任务场景：

1. **basic** - 基础模型，用于简单任务
2. **reasoning** - 推理模型，用于复杂推理任务
3. **vision** - 视觉模型，用于图像理解
4. **coding** - 编码模型，用于代码生成和分析
5. **planning** - 规划模型，用于任务规划和分解

每种类型对应配置文件中的一个节点（例如，`basic`类型对应`BASIC_MODEL`配置节点）。

## 使用方法

### 通过LLM工厂获取LLM

```python
from src.taskflow.llm_factory import llm_factory

# 根据LLM类型获取LLM
basic_llm = llm_factory.get_llm_by_type("basic")
response = basic_llm.invoke("你好，请介绍一下TaskFlow")

# 根据智能体类型获取LLM
planner_llm = llm_factory.get_llm_for_agent("planner")
executor_llm = llm_factory.get_llm_for_agent("executor")

# 根据任务类型获取LLM
code_llm = llm_factory.get_llm_for_task("code_generation") 
research_llm = llm_factory.get_llm_for_task("research")
```

### 创建自定义LLM

```python
from src.taskflow.llm_factory import llm_factory

# 创建自定义LLM
custom_llm = llm_factory.create_llm(
    model_name="gpt-4",
    temperature=0.7,
    max_tokens=2000
)
```

### 通过配置直接获取模型配置

```python
from src.taskflow.config.settings import settings

# 获取特定类型的LLM配置
basic_config = settings.llm.get_llm_config_by_type("basic")
```

## 智能体与LLM映射

TaskFlow使用映射表将智能体类型和任务类型映射到相应的LLM类型：

```python
# 智能体-LLM映射
AGENT_LLM_MAP: Dict[str, LLMType] = {
    "planner": "planning",
    "executor": "basic",
    "researcher": "reasoning",
    "coder": "coding",
    # ... 其他映射
}

# 任务-LLM映射
TASK_LLM_MAP: Dict[str, LLMType] = {
    "code_generation": "coding",
    "data_analysis": "reasoning",
    "research": "reasoning",
    # ... 其他映射
}
```

可以根据项目需要在`src/taskflow/config/agents.py`文件中调整这些映射关系。

## 环境变量支持

对于敏感信息和部署特定配置，可以使用环境变量：

1. 在`.env`文件中设置环境变量（开发环境）
2. 在配置文件中使用`${ENV_VAR}`语法引用环境变量
3. 在容器或生产环境中直接设置环境变量

## 缓存机制

TaskFlow使用LLM实例缓存来避免重复创建相同配置的LLM实例，提高性能。缓存可以通过以下方式控制：

```python
from src.taskflow.llm_factory import llm_factory

# 清除LLM缓存，释放资源
llm_factory.clear_cache()
```

## 配置加载顺序

TaskFlow按以下顺序查找配置文件：

1. 项目根目录下的`conf.taskflow.yaml`
2. 项目配置目录下的`conf.taskflow.yaml`
3. 用户主目录下的`.taskflow/conf.taskflow.yaml`
4. 系统配置目录`/etc/taskflow/conf.taskflow.yaml`

如果未找到任何配置文件，将使用代码中定义的默认值。 