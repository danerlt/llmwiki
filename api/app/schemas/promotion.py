import uuid

from pydantic import BaseModel


class PromotionCreate(BaseModel):
    to_kb_id: uuid.UUID
    note: str | None = None


class ReviewDecision(BaseModel):
    note: str | None = None


class PromotionOut(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    page_title: str
    to_kb_id: uuid.UUID
    to_kb_name: str
    requested_by: uuid.UUID
    status: str
    note: str | None = None
