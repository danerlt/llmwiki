import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base

PAGE_TYPES = ("index", "source_summary", "entity", "concept", "overview")


class WikiPage(Base):
    __tablename__ = "wiki_pages"
    __table_args__ = (UniqueConstraint("kb_id", "slug", name="uq_wiki_kb_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("knowledge_bases.id"))
    title: Mapped[str] = mapped_column(String(512))
    slug: Mapped[str] = mapped_column(String(512))
    page_type: Mapped[str] = mapped_column(String(32))
    content_md: Mapped[str] = mapped_column(Text, default="")
    frontmatter: Mapped[dict] = mapped_column(JSON, default=dict)
    source_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
