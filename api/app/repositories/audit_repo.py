import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent
from app.repositories.base_crud import BaseCrud


class AuditRepo(BaseCrud[AuditEvent]):
    """审计事件仓储：通用增删查继承自 BaseCrud，下为实体专属查询。"""

    def __init__(self) -> None:
        super().__init__(AuditEvent)

    async def create(
        self,
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
        self,
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

    async def count(self, session: AsyncSession, action: str | None = None) -> int:
        stmt = select(func.count()).select_from(AuditEvent)
        if action:
            stmt = stmt.where(AuditEvent.action == action)
        return int((await session.execute(stmt)).scalar() or 0)


audit_repo = AuditRepo()
