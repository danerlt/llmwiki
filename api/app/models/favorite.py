import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Favorite(Base):
    """用户收藏的页面。"""

    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "page_id", name="uq_favorite_user_page"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    page_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("wiki_pages.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
