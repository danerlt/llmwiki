import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey


async def create(
    session: AsyncSession, *, user_id: uuid.UUID, name: str, prefix: str, key_hash: str
) -> ApiKey:
    k = ApiKey(user_id=user_id, name=name, prefix=prefix, key_hash=key_hash)
    session.add(k)
    return k


async def get_by_hash(session: AsyncSession, key_hash: str) -> ApiKey | None:
    res = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked.is_(False))
    )
    return res.scalar_one_or_none()


async def list_by_user(session: AsyncSession, user_id: uuid.UUID) -> list[ApiKey]:
    res = await session.execute(
        select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
    )
    return list(res.scalars().all())


async def get_owned(
    session: AsyncSession, key_id: uuid.UUID, user_id: uuid.UUID
) -> ApiKey | None:
    res = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
    )
    return res.scalar_one_or_none()
