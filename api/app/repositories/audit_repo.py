import uuid

from sqlalchemy import desc, func, select
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


async def list_recent(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
) -> list[AuditEvent]:
    stmt = select(AuditEvent).order_by(desc(AuditEvent.created_at))
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    stmt = stmt.limit(limit).offset(offset)
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def count(session: AsyncSession, action: str | None = None) -> int:
    stmt = select(func.count()).select_from(AuditEvent)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    return int((await session.execute(stmt)).scalar() or 0)
