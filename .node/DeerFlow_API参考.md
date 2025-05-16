# DeerFlow API参考文档

## API概述

DeerFlow提供REST API接口，允许开发者以编程方式访问DeerFlow的功能。所有API都使用JSON进行数据交换，并通过HTTP协议提供。

### 基础URL

默认情况下，API服务运行在：

```
http://localhost:8000
```

可以通过命令行参数修改主机和端口：

```bash
python server.py --host 0.0.0.0 --port 9000
```

## API端点

### 1. 聊天流API

这是核心API，用于启动研究流程并获取流式响应。

**端点**: `/api/chat/stream`

**方法**: `POST`

**请求体**:

```json
{
  "thread_id": "string | __default__",
  "messages": [
    {
      "role": "user | system | assistant",
      "content": "string",
      "name": "string (可选)"
    }
  ],
  "max_plan_iterations": "number (默认: 1)",
  "max_step_num": "number (默认: 3)",
  "auto_accepted_plan": "boolean (默认: false)",
  "interrupt_feedback": "string (可选)",
  "enable_background_investigation": "boolean (默认: true)",
  "mcp_settings": {
    "servers": {
      "<server_name>": {
        "transport": "stdio | http",
        "command": "string (如果transport=stdio)",
        "args": ["string"],
        "url": "string (如果transport=http)",
        "enabled_tools": ["string"],
        "add_to_agents": ["researcher | coder"]
      }
    }
  }
}
```

**响应**: 事件流 (text/event-stream)

事件类型包括:
- `message_chunk`: 消息片段
- `tool_calls`: 工具调用
- `tool_call_chunks`: 工具调用片段
- `tool_call_result`: 工具调用结果
- `interrupt`: 中断请求（例如计划审查）

示例:
```
event: message_chunk
data: {"thread_id":"123","agent":"coordinator","id":"msg_1","role":"assistant","content":"正在分析您的问题..."}

event: interrupt
data: {"thread_id":"123","id":"int_1","role":"assistant","content":"请审查以下研究计划...","finish_reason":"interrupt","options":[{"text":"Edit plan","value":"edit_plan"},{"text":"Start research","value":"accepted"}]}
```

### 2. 文本转语音API

将文本转换为语音。

**端点**: `/api/tts`

**方法**: `POST`

**请求体**:

```json
{
  "text": "要转换为语音的文本",
  "encoding": "mp3",
  "speed_ratio": 1.0,
  "volume_ratio": 1.0,
  "pitch_ratio": 1.0,
  "text_type": "plain"
}
```

**响应**: 音频文件（MP3格式）

### 3. 播客生成API

生成基于研究报告的播客内容。

**端点**: `/api/podcast/generate`

**方法**: `POST`

**请求体**:

```json
{
  "title": "播客标题",
  "content": "研究报告内容",
  "locale": "en-US | zh-CN | ja-JP"
}
```

**响应**:

```json
{
  "title": "生成的播客标题",
  "podcast_script": "播客脚本",
  "audio_url": "生成的音频URL"
}
```

### 4. 演示文稿生成API

生成PowerPoint演示文稿。

**端点**: `/api/ppt/generate`

**方法**: `POST`

**请求体**:

```json
{
  "title": "演示文稿标题",
  "content": "研究报告内容",
  "locale": "en-US | zh-CN | ja-JP",
  "output_format": "pptx | pdf | html"
}
```

**响应**:

```json
{
  "title": "生成的演示文稿标题",
  "slides": [
    {
      "title": "幻灯片标题",
      "content": "幻灯片内容"
    }
  ],
  "download_url": "生成的演示文稿下载URL"
}
```

### 5. 散文生成API

增强文本内容。

**端点**: `/api/prose/generate`

**方法**: `POST`

**请求体**:

```json
{
  "title": "标题",
  "content": "原始内容",
  "action": "polish | summarize | expand",
  "locale": "en-US | zh-CN | ja-JP"
}
```

**响应**:

```json
{
  "title": "生成的标题",
  "content": "生成的内容"
}
```

### 6. MCP服务器元数据API

获取MCP服务器信息。

**端点**: `/api/mcp/server/metadata`

**方法**: `POST`

**请求体**:

```json
{
  "command": "string",
  "args": ["string"]
}
```

**响应**:

```json
{
  "name": "MCP服务器名称",
  "version": "版本",
  "tools": [
    {
      "name": "工具名称",
      "description": "工具描述",
      "parameters": {
        "type": "object",
        "properties": {}
      }
    }
  ]
}
```

## 错误处理

所有API错误使用标准HTTP状态码，并包含JSON格式的错误详情。

常见错误状态码:

- `400 Bad Request`: 请求格式错误
- `401 Unauthorized`: 认证失败
- `404 Not Found`: 资源不存在
- `500 Internal Server Error`: 服务器内部错误

错误响应格式:

```json
{
  "detail": "错误描述"
}
```

## 身份验证与安全

当前版本不包含内置身份验证机制。在生产环境中，建议在API前部署反向代理（如Nginx）并实现适当的身份验证和授权措施。

## 使用示例

### 启动研究会话 (使用cURL)

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "__default__",
    "messages": [
      {
        "role": "user",
        "content": "分析人工智能在医疗保健领域的应用"
      }
    ],
    "auto_accepted_plan": true,
    "enable_background_investigation": true
  }'
```

### 生成文本到语音 (使用cURL)

```bash
curl -X POST http://localhost:8000/api/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "欢迎使用DeerFlow智能研究系统",
    "speed_ratio": 1.0,
    "volume_ratio": 1.0,
    "pitch_ratio": 1.0
  }' \
  --output speech.mp3
```

### 生成演示文稿 (使用Python)

```python
import requests
import json

url = "http://localhost:8000/api/ppt/generate"
payload = {
    "title": "人工智能在医疗保健中的应用",
    "content": "研究报告全文...",
    "locale": "zh-CN",
    "output_format": "pptx"
}
headers = {"Content-Type": "application/json"}

response = requests.post(url, headers=headers, data=json.dumps(payload))
result = response.json()
print(f"演示文稿可在此下载: {result['download_url']}")
```

## 限制与注意事项

1. **并发请求**: API服务器基于uvicorn，默认支持适量并发请求。对于高负载场景，考虑使用Gunicorn作为ASGI服务器。

2. **请求超时**: 复杂研究可能需要较长处理时间，建议设置较长的客户端超时。

3. **数据量限制**: 
   - 请求体大小限制为10MB
   - TTS API文本限制为1024字符
   - 流式响应没有固定超时，但可能受底层LLM API限制

4. **依赖外部服务**: 
   - 搜索功能依赖配置的搜索引擎API
   - LLM功能依赖配置的模型提供商
   - TTS功能依赖volcengine API

5. **本地存储**: 
   - 演示文稿和播客音频等生成的文件临时存储在本地
   - 默认不提供持久化存储，可能需要额外的存储解决方案 