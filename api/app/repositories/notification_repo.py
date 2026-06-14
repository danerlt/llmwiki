import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


async def create(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: str,
    message: str,
    page_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
) -> Notification:
    n = Notification(
        user_id=user_id, type=type, message=message, page_id=page_id, actor_id=actor_id
    )
    session.add(n)
    return n


async def list_for(session: AsyncSession, user_id: uuid.UUID, limit: int = 30) -> list[Notification]:
    res = await session.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def unread_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    res = await session.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read.is_(False))
    )
    return int(res.scalar() or 0)


async def mark_all_read(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read.is_(False))
        .values(read=True)
    )
