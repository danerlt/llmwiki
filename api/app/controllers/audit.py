from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_db
from app.repositories import user_repo
from app.schemas.audit import AuditEventOut
from app.schemas.common import Paginated
from app.services import audit_service

router = APIRouter(tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("/audit", response_model=Paginated[AuditEventOut])
async def list_audit(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None, description="按动作精确过滤，如 page.create"),
    session: AsyncSession = Depends(get_db),
) -> Paginated[AuditEventOut]:
    total = await audit_service.count(session, action=action)
    events = await audit_service.list_recent(session, limit=limit, offset=offset, action=action)
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
