from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .errors import ErrorResult, MCPAdapterError, error_result
from .models import ChargeInput, Pet, PetList, PetQuery, RecordInput, WritePet
from .rest_client import RestClient


class IdInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    pet_id: str = Field(min_length=1)


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    q: str = Field(min_length=1)
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=20, ge=1, le=500)


class BatchDeleteInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ids: list[str] = Field(min_length=1)


async def _safe(call: Any) -> Any:
    try:
        return await call
    except MCPAdapterError as exc:
        return exc.result
    except Exception:
        return error_result("INTERNAL_ERROR", "MCP 服务内部错误")


def register_tools(server: Any, client: RestClient) -> None:
    @server.tool(name="list_pets", description="查询宠物档案列表。支持关键词、主人、种类、医生、疾病、状态、费用范围、排序和分页；返回档案列表及总数、总页数、费用汇总。")
    async def list_pets(query: PetQuery) -> PetList | ErrorResult:
        data = await _safe(client.get("/api/v1/pets", query.model_dump(exclude_none=True)))
        if isinstance(data, ErrorResult):
            return data
        try:
            return PetList.model_validate(data)
        except Exception:
            return error_result("BACKEND_INVALID_RESPONSE", "宠物列表响应不符合数据模型")

    @server.tool(name="get_pet", description="按档案编号获取一只宠物的完整档案、历史病历和消费明细。")
    async def get_pet(input: IdInput) -> Pet | ErrorResult:
        data = await _safe(client.get(f"/api/v1/pets/{input.pet_id}"))
        if isinstance(data, ErrorResult):
            return data
        try:
            return Pet.model_validate(data)
        except Exception:
            return error_result("BACKEND_INVALID_RESPONSE", "宠物详情响应不符合数据模型")

    @server.tool(name="create_pet", description="创建一份宠物档案。姓名、种类、主人、电话、医生和疾病为必填信息，档案编号由后端生成。")
    async def create_pet(input: WritePet) -> Pet | ErrorResult:
        data = await _safe(client.post("/api/v1/pets", input.model_dump()))
        if isinstance(data, ErrorResult):
            return data
        try:
            return Pet.model_validate(data)
        except Exception:
            return error_result("BACKEND_INVALID_RESPONSE", "新增宠物响应不符合数据模型")

    @server.tool(name="update_pet", description="全量更新宠物档案。未提供的字段会按后端规则清空。")
    async def update_pet(input: IdInput, pet: WritePet) -> Pet | ErrorResult:
        data = await _safe(client.put(f"/api/v1/pets/{input.pet_id}", pet.model_dump()))
        if isinstance(data, ErrorResult):
            return data
        try:
            return Pet.model_validate(data)
        except Exception:
            return error_result("BACKEND_INVALID_RESPONSE", "更新宠物响应不符合数据模型")

    @server.tool(name="patch_pet", description="局部更新宠物档案，只修改传入字段。")
    async def patch_pet(input: IdInput, fields: dict[str, Any]) -> Pet | ErrorResult:
        data = await _safe(client.patch(f"/api/v1/pets/{input.pet_id}", fields))
        if isinstance(data, ErrorResult):
            return data
        try:
            return Pet.model_validate(data)
        except Exception:
            return error_result("BACKEND_INVALID_RESPONSE", "局部更新响应不符合数据模型")

    @server.tool(name="delete_pet", description="删除一份宠物档案及其病历、消费明细。")
    async def delete_pet(input: IdInput) -> Any:
        return await _safe(client.delete(f"/api/v1/pets/{input.pet_id}"))

    @server.tool(name="search_pets", description="跨宠物档案和历史病历进行全文检索，空格分词按 AND 匹配。")
    async def search_pets(input: SearchInput) -> Any:
        return await _safe(client.get("/api/v1/pets/search", input.model_dump()))

    @server.tool(name="list_pet_records", description="查询指定宠物的历史病历。")
    async def list_pet_records(input: IdInput) -> Any:
        return await _safe(client.get(f"/api/v1/pets/{input.pet_id}/records"))

    @server.tool(name="add_pet_record", description="为指定宠物追加一条病历记录。")
    async def add_pet_record(input: IdInput, record: RecordInput) -> Any:
        return await _safe(client.post(f"/api/v1/pets/{input.pet_id}/records", record.model_dump()))

    @server.tool(name="list_pet_charges", description="查询指定宠物的消费明细。")
    async def list_pet_charges(input: IdInput) -> Any:
        return await _safe(client.get(f"/api/v1/pets/{input.pet_id}/charges"))

    @server.tool(name="add_pet_charge", description="为指定宠物追加一笔收费，后端会自动汇总总花费。")
    async def add_pet_charge(input: IdInput, charge: ChargeInput) -> Any:
        return await _safe(client.post(f"/api/v1/pets/{input.pet_id}/charges", charge.model_dump()))

    @server.tool(name="get_pet_summary", description="获取指定宠物的就诊次数、费用汇总和消费分类统计。")
    async def get_pet_summary(input: IdInput) -> Any:
        return await _safe(client.get(f"/api/v1/pets/{input.pet_id}/summary"))

    @server.tool(name="get_stats", description="获取宠物医院经营统计，包括档案数、病历数、收费笔数、收入和排行。")
    async def get_stats() -> Any:
        return await _safe(client.get("/api/v1/stats"))

    @server.tool(name="export_pets", description="导出全部宠物数据，format 支持 json 或 csv。")
    async def export_pets(format: str = "json") -> Any:
        if format not in {"json", "csv"}:
            return error_result("VALIDATION_ERROR", "format 必须是 json 或 csv")
        return await _safe(client.get("/api/v1/export", {"format": format}))

    @server.tool(name="compact_database", description="请求后端压实数据库文件，回收追加日志中的无效空间。")
    async def compact_database() -> Any:
        return await _safe(client.post("/api/v1/admin/compact"))

    @server.tool(name="batch_delete_pets", description="批量删除多份宠物档案。")
    async def batch_delete_pets(input: BatchDeleteInput) -> Any:
        return await _safe(client.post("/api/v1/pets/batch-delete", input.model_dump()))