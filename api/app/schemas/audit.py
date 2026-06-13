import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID
    actor_email: str
    action: str
    target_type: str | None = None
    target_id: uuid.UUID | None = None
    detail: dict | None = None
    created_at: datetime
