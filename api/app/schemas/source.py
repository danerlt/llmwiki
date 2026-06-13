import uuid

from pydantic import BaseModel


class SourceOut(BaseModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    filename: str
    content_type: str
    status: str
    error: str | None = None
    job_id: str | None = None

    model_config = {"from_attributes": True}


class SourceCreatedOut(BaseModel):
    source_id: uuid.UUID
    status: str
