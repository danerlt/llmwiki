import uuid

from pydantic import BaseModel


class KBOut(BaseModel):
    id: uuid.UUID
    scope_type: str
    scope_ref_id: uuid.UUID | None
    name: str

    model_config = {"from_attributes": True}
