"""MCP Streamable HTTP client integration for Stella."""

import asyncio
import hashlib
import json
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    url: str
    headers: dict[str, str]


class MCPClientManager:
    """Discover and invoke MCP tools while keeping server failures isolated."""

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConfig] = {}
        self._bindings: dict[str, tuple[MCPServerConfig, str]] = {}
        self._openai_tools: list[dict[str, Any]] = []
        self.errors: list[str] = []

    @classmethod
    def from_project(cls, project_root: Path | None = None) -> "MCPClientManager":
        manager = cls()
        config_path = (project_root or Path.cwd()) / ".mcp.json"
        if not config_path.is_file():
            return manager

        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            server_values = config.get("mcpServers")
            if not isinstance(server_values, dict):
                raise ValueError("mcpServers 必须是对象")
            for name, value in server_values.items():
                try:
                    manager._add_server(name, value)
                except (ValueError, TypeError) as exc:
                    manager.errors.append(f"跳过 MCP Server {name}：{exc}")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            manager.errors.append(f"无法读取 MCP 配置 {config_path}：{exc}")
            return manager

        manager._discover_all()
        return manager

    @property
    def openai_tools(self) -> list[dict[str, Any]]:
        return list(self._openai_tools)

    @property
    def status(self) -> str:
        if not self.errors:
            return ""
        return "MCP 连接提示：\n" + "\n".join(f"- {error}" for error in self.errors)

    def has_tool(self, exposed_name: str) -> bool:
        return exposed_name in self._bindings

    def execute(self, exposed_name: str, arguments: dict[str, Any]) -> str:
        binding = self._bindings.get(exposed_name)
        if binding is None:
            return f"错误：未知的 MCP 工具：{exposed_name}"
        server, tool_name = binding
        try:
            return _run_async(self._call_tool(server, tool_name, arguments))
        except Exception as exc:
            return f"错误：MCP Server {server.name} 的工具 {tool_name} 调用失败：{type(exc).__name__}: {exc}"

    def _add_server(self, name: Any, value: Any) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("MCP Server 名称不能为空")
        if not isinstance(value, dict):
            raise ValueError(f"MCP Server {name} 配置必须是对象")
        url = value.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError(f"MCP Server {name} 缺少 url")
        headers = value.get("headers", {})
        if not isinstance(headers, dict) or any(not isinstance(key, str) or not isinstance(item, str) for key, item in headers.items()):
            raise ValueError(f"MCP Server {name} 的 headers 必须是字符串键值对象")
        self._servers[name.strip()] = MCPServerConfig(name=name.strip(), url=url.strip(), headers=headers)

    def _discover_all(self) -> None:
        for server in self._servers.values():
            try:
                tools = _run_async(self._list_tools(server))
                for tool in tools:
                    self._register_tool(server, tool)
            except Exception as exc:
                self.errors.append(f"无法连接 MCP Server {server.name}（{server.url}）：{type(exc).__name__}: {exc}")

    def _register_tool(self, server: MCPServerConfig, tool: Any) -> None:
        tool_name = str(getattr(tool, "name", "")).strip()
        if not tool_name:
            return
        exposed_name = _exposed_tool_name(server.name, tool_name)
        if exposed_name in self._bindings:
            self.errors.append(f"MCP 工具名称冲突，已跳过：{exposed_name}")
            return
        schema = getattr(tool, "inputSchema", None)
        if not isinstance(schema, dict) or schema.get("type") != "object":
            schema = {"type": "object", "properties": {}}
        self._bindings[exposed_name] = (server, tool_name)
        self._openai_tools.append({
            "type": "function",
            "function": {
                "name": exposed_name,
                "description": str(getattr(tool, "description", "") or f"调用 MCP Server {server.name} 的工具 {tool_name}"),
                "parameters": schema,
            },
        })

    async def _list_tools(self, server: MCPServerConfig) -> list[Any]:
        async with _session_for(server) as session:
            result = await session.list_tools()
            return list(result.tools)

    async def _call_tool(self, server: MCPServerConfig, tool_name: str, arguments: dict[str, Any]) -> str:
        async with _session_for(server) as session:
            result = await session.call_tool(tool_name, arguments=arguments)
            return _format_tool_result(result)


def _exposed_tool_name(server_name: str, tool_name: str) -> str:
    base = f"mcp__{_safe_name(server_name)}__{_safe_name(tool_name)}"
    if len(base) <= 64:
        return base
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]
    return f"{base[:53]}__{digest}"


def _safe_name(value: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")
    return result or "server"


def _run_async(coroutine: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    raise RuntimeError("MCP 工具不能在已有 asyncio 事件循环中同步调用")


@asynccontextmanager
async def _session_for(server: MCPServerConfig):
    import httpx2
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    http_client = httpx2.AsyncClient(headers=server.headers or None)
    try:
        async with streamable_http_client(server.url, http_client=http_client) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session
    finally:
        await http_client.aclose()


def _format_tool_result(result: Any) -> str:
    sections: list[str] = []
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        sections.append(json.dumps(structured, ensure_ascii=False, default=str))
    for item in getattr(result, "content", []) or []:
        item_type = getattr(item, "type", "")
        if item_type == "text":
            sections.append(str(getattr(item, "text", "")))
        else:
            data = item.model_dump(mode="json") if hasattr(item, "model_dump") else str(item)
            sections.append(json.dumps(data, ensure_ascii=False, default=str) if isinstance(data, (dict, list)) else str(data))
    text = "\n".join(section for section in sections if section)
    if getattr(result, "isError", False):
        return f"错误：MCP 工具返回错误：{text or '未提供错误详情'}"
    return text or "MCP 工具调用成功，但没有返回内容。"