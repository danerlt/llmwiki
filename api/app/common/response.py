"""统一响应信封 Response[T]。

约定（见 plans/2026-06-14-backend-engineering-alignment.md 决策备注）：
- 成功：HTTP 200 + {success:true, code:"0", message:"ok", data:...}
- 业务异常：对应 HTTP 状态码 + {success:false, code, message, data:null, request_id}
即"统一信封形态 + 保留 HTTP 状态码语义"，前端 client.ts 单点拆包。
"""
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    model_config = ConfigDict(use_enum_values=True)  # ErrorCode 等枚举按其字符串值序列化

    success: bool = True
    code: str = "0"
    message: str = "ok"
    data: T | None = None
    request_id: str | None = None

    @classmethod
    def ok(cls, data: T | None = None, request_id: str | None = None) -> "Response[T]":
        return cls(success=True, code="0", message="ok", data=data, request_id=request_id)

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        request_id: str | None = None,
        data: T | None = None,
    ) -> "Response[T]":
        return cls(success=False, code=code, message=message, data=data, request_id=request_id)
