import uuid

from pydantic import BaseModel


class PageOut(BaseModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    title: str
    slug: str
    page_type: str

    model_config = {"from_attributes": True}


class PageDetailOut(PageOut):
    content_md: str
    frontmatter: dict
    source_ids: list[str]
