import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PromotionRequest


async def create(
    session: AsyncSession,
    *,
    page_id: uuid.UUID,
    to_kb_id: uuid.UUID,
    requested_by: uuid.UUID,
    note: str | None = None,
) -> PromotionRequest:
    pr = PromotionRequest(
        page_id=page_id, to_kb_id=to_kb_id, requested_by=requested_by, note=note
    )
    session.add(pr)
    return pr


async def get_by_id(session: AsyncSession, pr_id: uuid.UUID) -> PromotionRequest | None:
    res = await session.execute(select(PromotionRequest).where(PromotionRequest.id == pr_id))
    return res.scalar_one_or_none()


async def list_pending(session: AsyncSession) -> list[PromotionRequest]:
    res = await session.execute(
        select(PromotionRequest).where(PromotionRequest.status == "pending")
    )
    return list(res.scalars().all())
