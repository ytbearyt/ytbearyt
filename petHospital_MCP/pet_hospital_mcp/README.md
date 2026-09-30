# Pet Hospital MCP

独立的 Python MCP 适配服务，通过 HTTP 调用现有 Go 宠物医院 REST API，不修改 Go 后端。

## 环境与启动

要求 Python 3.11+，实际使用 `mcp==2.0.0`、Pydantic 2 和 HTTPX。

```powershell
cd pet_hospital_mcp
python -m pip install -e ".[test]"

# 先启动仓库根目录的 Go 服务
..\pethospital.exe -addr 127.0.0.1:8080

$env:PET_HOSPITAL_BASE_URL = "http://127.0.0.1:8080"
$env:MCP_HOST = "127.0.0.1"
$env:MCP_PORT = "8000"
python -m pet_hospital_mcp
```

MCP 端点为 `http://127.0.0.1:8000/mcp`，健康检查为 `http://127.0.0.1:8000/health`。
服务使用 SDK 2.x 的 `MCPServer` 和协议版本 `2026-07-28` 的 Streamable HTTP，启用无状态模式，不使用旧版 initialize、session id 或 SSE 会话恢复。

## 已提供工具

包含 `list_pets`、`get_pet`、`create_pet`、`update_pet`、`patch_pet`、`delete_pet`、`search_pets`、病历与收费工具、`get_pet_summary`、`get_stats`、`export_pets`、`compact_database` 和 `batch_delete_pets`。

`list_pets` 严格转发后端支持的 `q`、`name`、`ownerName`、`ownerPhone`、`species`、`doctor`、`disease`、`status`、`min`、`max`、`sortBy`、`order`、`page`、`pageSize` 参数。

通过 MCP Inspector 或 SDK 2.x 客户端连接上述 `/mcp`，发现工具后调用：

```json
{
  "query": {
    "species": "犬",
    "status": "待就诊",
    "page": 1,
    "pageSize": 20
  }
}
```

后端超时、不可用、HTTP 错误、无效 JSON 和内部错误会统一返回 `error.code`，不会泄露 HTTPX、Pydantic 或 Python 堆栈。

## 测试

```powershell
cd pet_hospital_mcp
pytest -q
```

测试只使用 HTTPX MockTransport/ASGI transport，不访问真实 Go 服务。

本次已实现档案管理及相关业务工具，未实现阶段二工具。