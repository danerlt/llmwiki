import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscription


async def add(session: AsyncSession, *, user_id: uuid.UUID, page_id: uuid.UUID) -> None:
    if not await exists(session, user_id=user_id, page_id=page_id):
        session.add(Subscription(user_id=user_id, page_id=page_id))


async def remove(session: AsyncSession, *, user_id: uuid.UUID, page_id: uuid.UUID) -> None:
    await session.execute(
        delete(Subscription).where(
            Subscription.user_id == user_id, Subscription.page_id == page_id
        )
    )


async def exists(session: AsyncSession, *, user_id: uuid.UUID, page_id: uuid.UUID) -> bool:
    res = await session.execute(
        select(Subscription.id).where(
            Subscription.user_id == user_id, Subscription.page_id == page_id
        )
    )
    return res.first() is not None


async def subscriber_ids(session: AsyncSession, page_id: uuid.UUID) -> list[uuid.UUID]:
    res = await session.execute(
        select(Subscription.user_id).where(Subscription.page_id == page_id)
    )
    return [r[0] for r in res.all()]
