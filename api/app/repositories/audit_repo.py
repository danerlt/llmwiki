import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


async def create(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    action: str,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    detail: dict | None = None,
) -> AuditEvent:
    ev = AuditEvent(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    session.add(ev)
    return ev


async def list_recent(session: AsyncSession, limit: int = 100) -> list[AuditEvent]:
    res = await session.execute(
        select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(limit)
    )
    return list(res.scalars().all())
