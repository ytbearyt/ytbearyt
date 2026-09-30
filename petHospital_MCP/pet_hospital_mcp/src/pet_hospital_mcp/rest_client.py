import asyncio
from typing import Any

import httpx

from .config import Settings
from .errors import MCPAdapterError


class RestClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(base_url=settings.backend_url, timeout=settings.timeout_seconds)

    async def close(self) -> None:
        await self.client.aclose()

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.settings.retries + 1):
            try:
                response = await self.client.request(method, path, **kwargs)
                if response.status_code >= 500 and attempt < self.settings.retries:
                    await asyncio.sleep(0.05 * (attempt + 1))
                    continue
                if response.status_code >= 400:
                    raise MCPAdapterError("BACKEND_API_ERROR", "宠物医院后端请求失败", {"status": response.status_code})
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise MCPAdapterError("BACKEND_INVALID_RESPONSE", "后端返回了无效 JSON") from exc
                if not isinstance(payload, dict) or payload.get("code") != 200:
                    raise MCPAdapterError("BACKEND_INVALID_RESPONSE", "后端返回格式不符合约定")
                return payload.get("data")
            except MCPAdapterError:
                raise
            except (httpx.TimeoutException, TimeoutError) as exc:
                last_error = exc
                if attempt < self.settings.retries:
                    continue
                raise MCPAdapterError("BACKEND_TIMEOUT", "连接宠物医院后端超时") from exc
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self.settings.retries:
                    continue
                raise MCPAdapterError("BACKEND_UNAVAILABLE", "宠物医院后端不可用") from exc
        raise MCPAdapterError("BACKEND_UNAVAILABLE", "宠物医院后端不可用") from last_error

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, json: Any = None, params: dict[str, Any] | None = None) -> Any:
        return await self.request("POST", path, json=json, params=params)

    async def put(self, path: str, json: Any = None) -> Any:
        return await self.request("PUT", path, json=json)

    async def patch(self, path: str, json: Any = None) -> Any:
        return await self.request("PATCH", path, json=json)

    async def delete(self, path: str) -> Any:
        return await self.request("DELETE", path)