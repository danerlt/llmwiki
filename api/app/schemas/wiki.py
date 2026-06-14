import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# 人工可创建/编辑的页类型（index 目录、source_summary 源摘要为系统自动生成，不可手工指定）
HUMAN_PAGE_TYPES = ("overview", "entity", "concept")


class PageCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    slug: str | None = Field(default=None, max_length=512)
    content_md: str = Field(default="", max_length=200_000)
    page_type: str = Field(default="concept")
    tags: list[str] = Field(default_factory=list, max_length=30)


class PageUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    content_md: str | None = Field(default=None, max_length=200_000)
    page_type: str | None = None
    tags: list[str] | None = Field(default=None, max_length=30)


class PageVersionOut(BaseModel):
    version_no: int
    title: str
    page_type: str
    content_md: str
    edited_by: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PageOut(BaseModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    title: str
    slug: str
    page_type: str
    tags: list[str] = []

    model_config = {"from_attributes": True}


class SourceRef(BaseModel):
    id: uuid.UUID
    filename: str


class SearchHit(PageOut):
    snippet: str = ""
    matched: str = ""


class PageDetailOut(PageOut):
    content_md: str
    frontmatter: dict
    source_ids: list[str]
    updated_at: datetime | None = None
    is_favorited: bool = False
    is_subscribed: bool = False
    backlinks: list[PageOut] = []
    outlinks: list[PageOut] = []
    sources: list[SourceRef] = []


class StatsOut(BaseModel):
    kb_count: int
    page_count: int
    source_count: int
    pending_reviews: int
