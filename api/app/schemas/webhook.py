import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WebhookCreate(BaseModel):
    url: str = Field(min_length=8, max_length=1024)
    secret: str = Field(min_length=8, max_length=64)


class WebhookOut(BaseModel):
    id: uuid.UUID
    url: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
