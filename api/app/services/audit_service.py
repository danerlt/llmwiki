import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent
from app.repositories import audit_repo


async def record(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    action: str,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    detail: dict | None = None,
) -> AuditEvent:
    """记录一条审计事件（不 commit，由调用方与业务变更同事务提交）。"""
    return await audit_repo.create(
        session,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )


async def list_recent(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
) -> list[AuditEvent]:
    return await audit_repo.list_recent(session, limit=limit, offset=offset, action=action)


async def count(session: AsyncSession, action: str | None = None) -> int:
    return await audit_repo.count(session, action=action)
