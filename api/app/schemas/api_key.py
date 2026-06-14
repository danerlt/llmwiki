import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    revoked: bool
    created_at: datetime
    last_used_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyOut):
    key: str  # 明文，仅创建时返回一次
