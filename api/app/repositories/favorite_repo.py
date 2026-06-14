import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Favorite, WikiPage


async def add(session: AsyncSession, *, user_id: uuid.UUID, page_id: uuid.UUID) -> None:
    if not await exists(session, user_id=user_id, page_id=page_id):
        session.add(Favorite(user_id=user_id, page_id=page_id))


async def remove(session: AsyncSession, *, user_id: uuid.UUID, page_id: uuid.UUID) -> None:
    await session.execute(
        delete(Favorite).where(Favorite.user_id == user_id, Favorite.page_id == page_id)
    )


async def exists(session: AsyncSession, *, user_id: uuid.UUID, page_id: uuid.UUID) -> bool:
    res = await session.execute(
        select(Favorite.id).where(Favorite.user_id == user_id, Favorite.page_id == page_id)
    )
    return res.first() is not None


async def list_pages(session: AsyncSession, user_id: uuid.UUID) -> list[WikiPage]:
    res = await session.execute(
        select(WikiPage)
        .join(Favorite, Favorite.page_id == WikiPage.id)
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc())
    )
    return list(res.scalars().all())
