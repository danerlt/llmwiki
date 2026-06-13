import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PageVersion(Base):
    """页的历史版本快照。每次人工更新/回滚前，把被覆盖的旧状态存为一个版本，支持查看与回滚。"""

    __tablename__ = "page_versions"
    __table_args__ = (UniqueConstraint("page_id", "version_no", name="uq_pageversion_page_no"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("wiki_pages.id"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer)  # 1 起，按页单调递增
    title: Mapped[str] = mapped_column(String(512))
    page_type: Mapped[str] = mapped_column(String(32))
    content_md: Mapped[str] = mapped_column(Text, default="")
    edited_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
