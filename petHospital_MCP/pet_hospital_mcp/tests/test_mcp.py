import httpx
import pytest
from pydantic import ValidationError

from pet_hospital_mcp.config import Settings
from pet_hospital_mcp.errors import MCPAdapterError
from pet_hospital_mcp.models import PetQuery
from pet_hospital_mcp.rest_client import RestClient
from pet_hospital_mcp.server import create_server


@pytest.mark.asyncio
async def test_list_request_forwards_all_supported_query_parameters():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"code": 200, "data": {"ok": True}})

    client = RestClient(Settings(retries=0), httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test"))
    await client.get("/api/v1/pets", {"q": "小白", "species": "犬", "page": 2, "pageSize": 50, "min": 10, "max": 99, "sortBy": "totalCost", "order": "desc"})
    await client.close()
    assert seen == {"q": "小白", "species": "犬", "page": "2", "pageSize": "50", "min": "10", "max": "99", "sortBy": "totalCost", "order": "desc"}


def test_query_rejects_invalid_values_and_unknown_fields():
    with pytest.raises(ValidationError):
        PetQuery(species="鱼")
    with pytest.raises(ValidationError):
        PetQuery(min=10, max=1)
    with pytest.raises(ValidationError):
        PetQuery(pageSize=501)
    with pytest.raises(ValidationError):
        PetQuery(extra="bad")


@pytest.mark.asyncio
async def test_backend_4xx_is_normalized():
    transport = httpx.MockTransport(lambda request: httpx.Response(404, json={"code": 404}))
    client = RestClient(Settings(retries=0), httpx.AsyncClient(transport=transport, base_url="http://test"))
    with pytest.raises(MCPAdapterError) as error:
        await client.get("/api/v1/pets/PET-404")
    assert error.value.result.error.code == "BACKEND_API_ERROR"
    await client.close()


@pytest.mark.asyncio
async def test_tools_and_stateless_app_are_exposed():
    server, client = create_server(Settings())
    tools = await server.list_tools()
    names = {tool.name for tool in tools}
    assert {"list_pets", "create_pet", "add_pet_record", "add_pet_charge", "get_stats"} <= names
    app = server.streamable_http_app(stateless_http=True, json_response=True)
    response = await httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test").get("/health")
    assert response.json()["status"] == "ok"
    await client.close()