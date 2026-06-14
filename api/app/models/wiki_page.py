import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base

PAGE_TYPES = ("index", "source_summary", "entity", "concept", "overview")


class WikiPage(Base):
    __tablename__ = "wiki_pages"
    __table_args__ = (
        UniqueConstraint("kb_id", "slug", name="uq_wiki_kb_slug"),
        # GIN trgm 索引：与迁移 3aa55dd6fe75 直建的 DDL 对齐，纳入 metadata 后 autogenerate 不再误删
        Index(
            "ix_wiki_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "ix_wiki_content_trgm",
            "content_md",
            postgresql_using="gin",
            postgresql_ops={"content_md": "gin_trgm_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("knowledge_bases.id"), index=True)
    title: Mapped[str] = mapped_column(String(512))
    slug: Mapped[str] = mapped_column(String(512))
    page_type: Mapped[str] = mapped_column(String(32))
    content_md: Mapped[str] = mapped_column(Text, default="")
    frontmatter: Mapped[dict] = mapped_column(JSON, default=dict)
    source_ids: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # 内容认证（专家背书）：经 can_write 用户认证为权威内容
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
