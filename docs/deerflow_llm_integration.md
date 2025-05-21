# DeerFlow LLM集成指南

本文档介绍了将DeerFlow的LLM配置和调用方式集成到TaskFlow中的实现过程和使用方法。

## 背景

DeerFlow项目采用了简洁高效的LLM配置和调用方式，特点是：

1. 使用类型映射表(`AGENT_LLM_MAP`)，将不同的智能体映射到特定的LLM类型
2. 通过简单的`get_llm_by_type`函数获取LLM实例
3. 基于YAML文件的配置加载
4. 缓存机制避免重复创建LLM实例

TaskFlow采用了更灵活的工厂和注册表模式，但在某些场景下，DeerFlow的直接调用方式可能更简洁易用。

## 集成方案

我们采用了"增强式整合"方案，保留TaskFlow的核心架构，同时引入DeerFlow风格的简便调用方式：

1. 创建智能体-LLM类型映射，类似于DeerFlow的`AGENT_LLM_MAP`
2. 实现`get_llm_by_type`等简化函数
3. 增强LLM工厂类，添加类型缓存和配置加载
4. 提供类似DeerFlow的配置文件格式

## 实现文件

本次集成涉及以下文件：

1. `src/taskflow/config/agents.py` - 定义LLM类型和映射关系
2. `src/taskflow/llm_factory.py` - 增强LLM工厂和提供简化接口
3. `src/taskflow/config/loader.py` - 实现配置加载功能
4. `conf.taskflow.yaml.example` - 提供配置示例
5. `examples/llm_usage_example.py` - 使用示例

## 使用说明

### 配置LLM

1. 复制`conf.taskflow.yaml.example`为`conf.taskflow.yaml`
2. 根据需要修改各个LLM类型的配置：

```yaml
# 基础模型配置
BASIC_MODEL:
  model: "gpt-3.5-turbo-1106"
  temperature: 0.0
  max_tokens: 4000
  api_key: "${OPENAI_API_KEY}"
  base_url: "${OPENAI_API_BASE}"

# 推理模型配置
REASONING_MODEL:
  model: "gpt-4-turbo-preview"
  # ... 其他配置
```

### 使用LLM

#### 1. 基于类型获取LLM

```python
from src.taskflow.llm_factory import get_llm_by_type

# 获取基础LLM
basic_llm = get_llm_by_type("basic")
response = basic_llm.invoke("你好，请介绍一下TaskFlow")

# 获取推理LLM
reasoning_llm = get_llm_by_type("reasoning")
response = reasoning_llm.invoke("分析量子计算对密码学的影响")
```

#### 2. 基于智能体或任务获取LLM

```python
from src.taskflow.llm_factory import get_llm_for_agent, get_llm_for_task

# 基于智能体获取LLM
planner_llm = get_llm_for_agent("planner")
researcher_llm = get_llm_for_agent("researcher")

# 基于任务获取LLM
code_llm = get_llm_for_task("code_generation")
research_llm = get_llm_for_task("research")
```

#### 3. 使用LLM工厂创建自定义LLM

```python
from src.taskflow.llm_factory import llm_factory

# 创建自定义LLM
custom_llm = llm_factory.create_llm(
    model_name="gpt-4",
    temperature=0.7,
    max_tokens=2000
)
```

#### 4. 创建LLM链

```python
from src.taskflow.llm_factory import llm_factory

# 创建简单的LLM链
prompt_template = "你是一位{role}。请{action}关于{topic}的内容。"

chain = llm_factory.create_chain(
    prompt_template=prompt_template,
    model_name="gpt-3.5-turbo",
    temperature=0.0
)

response = chain.invoke({
    "role": "Python专家",
    "action": "解释",
    "topic": "Python装饰器"
})
```

## 智能体-LLM映射

智能体和任务通过以下映射表映射到相应的LLM类型：

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

可以根据项目需要修改这些映射关系。

## 高级用法

完整的高级用法示例可以查看`examples/llm_usage_example.py`文件，包括：

1. 直接调用LLM
2. 创建带结构化输出的LLM
3. 使用LLM链处理复杂任务

## 注意事项

1. 确保环境变量或配置文件中设置了正确的API密钥
2. 对于需要大量处理的任务，建议使用异步方法(`ainvoke`)
3. 可以通过`llm_factory.clear_cache()`清除LLM实例缓存，释放资源 