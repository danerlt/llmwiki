import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PageLink(Base):
    __tablename__ = "page_links"

    from_page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("wiki_pages.id"), primary_key=True
    )
    to_slug: Mapped[str] = mapped_column(String(512), primary_key=True)
    to_page_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wiki_pages.id"), nullable=True
    )
