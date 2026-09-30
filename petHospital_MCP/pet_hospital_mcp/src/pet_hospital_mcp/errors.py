from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ErrorBody


class MCPAdapterError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.result = ErrorResult(error=ErrorBody(code=code, message=message, details=details or {}))


def error_result(code: str, message: str, details: dict[str, Any] | None = None) -> ErrorResult:
    return ErrorResult(error=ErrorBody(code=code, message=message, details=details or {}))