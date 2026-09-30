import os
import json
import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

# AnythingLLM配置
ANYTHINGLLM_BASE = os.getenv("ANYTHINGLLM_BASE", "http://localhost:3001")
ANYTHINGLLM_API_KEY = os.getenv("ANYTHINGLLM_API_KEY", "")
WORKSPACE_SLUG = os.getenv("WORKSPACE_SLUG", "")

# MCP工具定义
TOOLS = [
    {
        "name": "ask_workspace",
        "description": "向AnythingLLM工作区提问并获取AI回答",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "要问工作区的问题"
                }
            },
            "required": ["question"]
        }
    },
    {
        "name": "get_workspace",
        "description": "获取当前AnythingLLM工作区的配置、文档和线程摘要",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "list_workspace_chats",
        "description": "获取当前工作区的聊天记录",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "返回消息数量，范围1-1000，默认100",
                    "minimum": 1,
                    "maximum": 1000
                },
                "order_by": {
                    "type": "string",
                    "description": "排序方式：asc或desc",
                    "enum": ["asc", "desc"]
                },
                "api_session_id": {
                    "type": "string",
                    "description": "可选的API会话ID"
                }
            }
        }
    },
    {
        "name": "vector_search",
        "description": "在当前工作区的文档中执行向量相似度搜索",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索问题或关键词"},
                "top_n": {
                    "type": "integer",
                    "description": "最多返回的结果数，范围1-50，默认4",
                    "minimum": 1,
                    "maximum": 50
                },
                "score_threshold": {
                    "type": "number",
                    "description": "可选的最低相似度分数，范围0-1",
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": ["query"]
        }
    }
]

async def call_api(method: str, path: str, **kwargs) -> dict:
    """调用AnythingLLM API，并将非成功响应转换为可读错误。"""
    if not ANYTHINGLLM_API_KEY:
        raise RuntimeError("未设置 ANYTHINGLLM_API_KEY")

    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method,
            f"{ANYTHINGLLM_BASE.rstrip('/')}{path}",
            headers={
                "Authorization": f"Bearer {ANYTHINGLLM_API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=60.0,
            **kwargs
        )
        try:
            data = resp.json()
        except ValueError:
            data = {"error": resp.text or "AnythingLLM返回了无效响应"}
        if resp.is_error:
            message = data.get("error") or data.get("message") or resp.reason_phrase
            raise RuntimeError(f"AnythingLLM API错误 ({resp.status_code}): {message}")
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(str(data["error"]))
        return data


def require_workspace() -> str:
    if not WORKSPACE_SLUG:
        raise RuntimeError("未设置 WORKSPACE_SLUG")
    return WORKSPACE_SLUG


async def call_anythingllm(question: str) -> str:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question不能为空")
    data = await call_api(
        "POST",
        f"/api/v1/workspace/{require_workspace()}/chat",
        json={"message": question.strip(), "mode": "query"}
    )
    return data.get("textResponse", "无响应")


async def get_workspace() -> dict:
    return await call_api("GET", f"/api/v1/workspace/{require_workspace()}")


async def list_workspace_chats(args: dict) -> dict:
    params = {}
    if args.get("limit") is not None:
        limit = args["limit"]
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("limit必须是1到1000之间的整数")
        params["limit"] = limit
    if args.get("order_by") is not None:
        if args["order_by"] not in ("asc", "desc"):
            raise ValueError("order_by必须是asc或desc")
        params["orderBy"] = args["order_by"]
    if args.get("api_session_id"):
        params["apiSessionId"] = args["api_session_id"]
    return await call_api("GET", f"/api/v1/workspace/{require_workspace()}/chats", params=params)


async def vector_search(args: dict) -> dict:
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query不能为空")
    top_n = args.get("top_n", 4)
    if not isinstance(top_n, int) or isinstance(top_n, bool) or not 1 <= top_n <= 50:
        raise ValueError("top_n必须是1到50之间的整数")
    score_threshold = args.get("score_threshold")
    if score_threshold is not None and (
        not isinstance(score_threshold, (int, float)) or isinstance(score_threshold, bool)
        or not 0 <= score_threshold <= 1
    ):
        raise ValueError("score_threshold必须在0到1之间")
    payload = {"query": query.strip(), "topN": top_n}
    if score_threshold is not None:
        payload["scoreThreshold"] = score_threshold
    return await call_api(
        "POST",
        f"/api/v1/workspace/{require_workspace()}/vector-search",
        json=payload
    )

async def handle_mcp(request: Request) -> JSONResponse:
    """处理MCP JSON-RPC请求"""
    body = await request.json()
    method = body.get("method")
    req_id = body.get("id")

    # tools/list
    if method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS}
        })

    # tools/call
    if method == "tools/call":
        tool_name = body.get("params", {}).get("name")
        args = body.get("params", {}).get("arguments", {})

        try:
            if tool_name == "ask_workspace":
                answer = await call_anythingllm(args.get("question", ""))
            elif tool_name == "get_workspace":
                answer = json.dumps(await get_workspace(), ensure_ascii=False, indent=2)
            elif tool_name == "list_workspace_chats":
                answer = json.dumps(await list_workspace_chats(args), ensure_ascii=False, indent=2)
            elif tool_name == "vector_search":
                answer = json.dumps(await vector_search(args), ensure_ascii=False, indent=2)
            else:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                })
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": answer}]}
            })
        except (ValueError, RuntimeError) as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": str(e)}
            })
        except Exception as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)}
            })

    return JSONResponse({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"}
    })

app = Starlette(routes=[Route("/mcp", handle_mcp, methods=["POST"])])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
