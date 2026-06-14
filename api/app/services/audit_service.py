import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent
from app.repositories import audit_repo, user_repo
from app.schemas.audit import AuditEventOut
from app.schemas.common import Paginated


class AuditService:
    async def record(
        self,
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
        self,
        session: AsyncSession,
        limit: int = 50,
        offset: int = 0,
        action: str | None = None,
    ) -> list[AuditEvent]:
        return await audit_repo.list_recent(session, limit=limit, offset=offset, action=action)

    async def count(self, session: AsyncSession, action: str | None = None) -> int:
        return await audit_repo.count(session, action=action)

    async def list_events(
        self,
        session: AsyncSession,
        *,
        limit: int,
        offset: int,
        action: str | None = None,
    ) -> Paginated[AuditEventOut]:
        """分页列出审计事件，并补全操作者邮箱后转换为输出 schema。"""
        total = await audit_repo.count(session, action=action)
        events = await audit_repo.list_recent(session, limit=limit, offset=offset, action=action)
        items: list[AuditEventOut] = []
        for ev in events:
            actor = await user_repo.get_by_id(session, ev.actor_id)
            items.append(
                AuditEventOut(
                    id=ev.id,
                    actor_id=ev.actor_id,
                    actor_email=actor.email if actor else "(未知)",
                    action=ev.action,
                    target_type=ev.target_type,
                    target_id=ev.target_id,
                    detail=ev.detail,
                    created_at=ev.created_at,
                )
            )
        return Paginated(items=items, total=total, limit=limit, offset=offset)

    async def export_rows(self, session: AsyncSession, *, action: str | None = None) -> list[list[str]]:
        """导出用的扁平行数据（不含表头），供 controller 写入 CSV。"""
        events = await audit_repo.list_recent(session, limit=10000, offset=0, action=action)
        rows: list[list[str]] = []
        for ev in events:
            actor = await user_repo.get_by_id(session, ev.actor_id)
            rows.append(
                [
                    ev.created_at.isoformat() if ev.created_at else "",
                    actor.email if actor else "(未知)",
                    ev.action,
                    ev.target_type or "",
                    str(ev.target_id) if ev.target_id else "",
                    json.dumps(ev.detail, ensure_ascii=False) if ev.detail else "",
                ]
            )
        return rows


audit_service = AuditService()
