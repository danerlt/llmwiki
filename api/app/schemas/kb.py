import uuid

from pydantic import BaseModel


class KBOut(BaseModel):
    id: uuid.UUID
    scope_type: str
    scope_ref_id: uuid.UUID | None
    name: str
    page_count: int = 0

    model_config = {"from_attributes": True}
