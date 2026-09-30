from contextlib import asynccontextmanager

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import Settings
from .rest_client import RestClient
from .tools import register_tools


def create_server(settings: Settings | None = None) -> tuple[MCPServer, RestClient]:
    settings = settings or Settings.from_env()
    client = RestClient(settings)
    server = MCPServer(name="pet-hospital", version="0.2.0", description="宠物医院 REST API 的 MCP 适配服务")
    register_tools(server, client)

    @server.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "pet-hospital-mcp"})

    return server, client


async def run(settings: Settings | None = None) -> None:
    settings = settings or Settings.from_env()
    server, client = create_server(settings)
    try:
        await server.run_streamable_http_async(
            host=settings.host,
            port=settings.port,
            stateless_http=True,
            streamable_http_path="/mcp",
            json_response=True,
        )
    finally:
        await client.close()