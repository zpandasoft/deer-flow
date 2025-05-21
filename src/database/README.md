# 智能体LLM调用数据保存功能

本模块实现了对多智能体系统中所有LLM调用的自动保存功能，核心实现包括：

## 数据库表设计

`agent_llm_calls` 表用于存储所有智能体的LLM调用记录，包括以下字段：

- `call_id`: 调用ID (主键)
- `agent_name`: 智能体名称
- `node_name`: 节点名称
- `reference_id`: 关联ID (objective_id, task_id 或 step_id)
- `reference_type`: 关联类型 (OBJECTIVE, TASK, STEP)
- `input_data`: 输入数据 (提示词+上下文)
- `output_data`: 输出数据 (LLM响应)
- `tokens_used`: 使用的token数
- `duration_ms`: 调用持续时间 (毫秒)
- `status`: 状态 (SUCCESS, FAILED)
- `error_message`: 错误信息 (如果失败)
- `created_at`: 创建时间
- `model_name`: 模型名称
- `metadata`: 其他元数据

## 实现方式

1. **装饰器模式**: 使用 `wrap_create_agent` 装饰器拦截所有智能体创建，自动应用 `log_llm_call` 装饰器到每个智能体函数。

2. **工作流集成**: 在每个节点函数中添加当前节点名称 (`current_node`) 到状态中，确保在记录LLM调用时能够正确标识来源节点。

3. **数据库服务**: `MySQLService` 类提供数据库连接和查询功能，通过全局单例方式管理数据库连接。

## 使用方法

当系统初始化时，`init_db_connection()` 会自动创建数据库连接。当智能体被调用时，装饰器会自动记录调用数据到数据库中。

## 初始化数据库

使用以下命令初始化数据库和表：

```bash
python scripts/init_db.py
```

## 查询示例

```sql
-- 查看所有调用记录
SELECT * FROM agent_llm_calls ORDER BY created_at DESC LIMIT 10;

-- 查看失败的调用
SELECT * FROM agent_llm_calls WHERE status = 'FAILED' ORDER BY created_at DESC;

-- 按智能体名称统计调用次数
SELECT agent_name, COUNT(*) as call_count 
FROM agent_llm_calls 
GROUP BY agent_name 
ORDER BY call_count DESC;

-- 按节点名称统计平均调用耗时
SELECT node_name, AVG(duration_ms) as avg_duration 
FROM agent_llm_calls 
WHERE status = 'SUCCESS'
GROUP BY node_name 
ORDER BY avg_duration DESC;
``` 