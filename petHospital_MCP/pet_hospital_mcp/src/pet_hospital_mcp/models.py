from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Species = Literal["犬", "猫", "兔", "鸟", "仓鼠", "爬宠", "其他"]
Status = Literal["待就诊", "就诊中", "住院中", "已康复", "慢性病随访"]
SortField = Literal["id", "name", "ownerName", "species", "doctor", "disease", "status", "totalCost", "visitCount", "createdAt", "updatedAt"]
Order = Literal["asc", "desc"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PetQuery(StrictModel):
    q: str | None = None
    name: str | None = None
    ownerName: str | None = None
    ownerPhone: str | None = None
    species: Species | None = None
    doctor: str | None = None
    disease: str | None = None
    status: Status | None = None
    min: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    sortBy: SortField | None = None
    order: Order | None = None
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=20, ge=1, le=500)

    @model_validator(mode="after")
    def validate_range(self) -> "PetQuery":
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min must be less than or equal to max")
        return self


class Pet(StrictModel):
    id: str
    name: str
    species: str
    breed: str = ""
    gender: str = ""
    ageMonths: int | None = None
    color: str = ""
    chipNo: str = ""
    ownerName: str
    ownerPhone: str
    ownerAddr: str = ""
    doctor: str
    disease: str
    status: str = ""
    allergy: str = ""
    note: str = ""
    records: list[dict[str, Any]] = Field(default_factory=list)
    charges: list[dict[str, Any]] = Field(default_factory=list)
    totalCost: float = 0
    visitCount: int = 0
    model_config = ConfigDict(extra="allow", strict=True)


class PetList(StrictModel):
    items: list[Pet]
    total: int
    page: int
    pageSize: int
    totalPages: int
    totalCost: float


class WritePet(StrictModel):
    name: str = Field(min_length=1)
    species: Species
    breed: str = ""
    gender: str = ""
    ageMonths: int | None = Field(default=None, ge=0)
    color: str = ""
    chipNo: str = ""
    ownerName: str = Field(min_length=1)
    ownerPhone: str = Field(min_length=1)
    ownerAddr: str = ""
    doctor: str = Field(min_length=1)
    disease: str = Field(min_length=1)
    status: Status = "待就诊"
    allergy: str = ""
    note: str = ""


class RecordInput(StrictModel):
    date: str = Field(min_length=1)
    diagnosis: str = Field(min_length=1)
    treatment: str = ""
    doctor: str = ""
    note: str = ""


class ChargeInput(StrictModel):
    date: str = Field(min_length=1)
    item: str = Field(min_length=1)
    category: str = Field(min_length=1)
    amount: float = Field(gt=0, allow_inf_nan=False)
    note: str = ""