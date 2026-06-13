import uuid
from datetime import datetime

from pydantic import BaseModel


class PageOut(BaseModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    title: str
    slug: str
    page_type: str

    model_config = {"from_attributes": True}


class SourceRef(BaseModel):
    id: uuid.UUID
    filename: str


class PageDetailOut(PageOut):
    content_md: str
    frontmatter: dict
    source_ids: list[str]
    updated_at: datetime | None = None
    backlinks: list[PageOut] = []
    sources: list[SourceRef] = []


class StatsOut(BaseModel):
    kb_count: int
    page_count: int
    source_count: int
    pending_reviews: int
