import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Webhook


async def create(
    session: AsyncSession, *, created_by: uuid.UUID, url: str, secret: str
) -> Webhook:
    w = Webhook(created_by=created_by, url=url, secret=secret)
    session.add(w)
    return w


async def list_all(session: AsyncSession) -> list[Webhook]:
    res = await session.execute(select(Webhook).order_by(Webhook.created_at.desc()))
    return list(res.scalars().all())


async def list_active(session: AsyncSession) -> list[Webhook]:
    res = await session.execute(select(Webhook).where(Webhook.active.is_(True)))
    return list(res.scalars().all())


async def get_by_id(session: AsyncSession, webhook_id: uuid.UUID) -> Webhook | None:
    res = await session.execute(select(Webhook).where(Webhook.id == webhook_id))
    return res.scalar_one_or_none()
