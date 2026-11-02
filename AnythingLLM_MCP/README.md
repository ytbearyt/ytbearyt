# AnythingLLM MCP Server

向AnythingLLM工作区提问的MCP Server。

## 配置

设置环境变量：
```bash
set ANYTHINGLLM_BASE=http://localhost:3001
set ANYTHINGLLM_API_KEY=your-api-key
set WORKSPACE_SLUG=your-workspace-slug
```

`ANYTHINGLLM_API_KEY` 和 `WORKSPACE_SLUG` 必须显式配置，服务不会使用内置密钥或工作区。

## 启动

```bash
python server.py
```

服务器运行在 http://localhost:8080/mcp

## 测试

```bash
# 列出工具
curl -X POST http://localhost:8080/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# 提问
curl -X POST http://localhost:8080/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ask_workspace","arguments":{"question":"你的问题"}}}'
```

## 工具

- `ask_workspace`：向工作区提问。
- `get_workspace`：获取工作区配置、文档和线程摘要。
- `list_workspace_chats`：获取聊天记录，可传 `limit`、`order_by` 和 `api_session_id`。
- `vector_search`：搜索工作区文档，可传 `top_n` 和 `score_threshold`。
