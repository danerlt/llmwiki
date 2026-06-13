from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_db
from app.repositories import user_repo
from app.schemas.audit import AuditEventOut
from app.services import audit_service

router = APIRouter(tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("/audit", response_model=list[AuditEventOut])
async def list_audit(session: AsyncSession = Depends(get_db)):
    out: list[AuditEventOut] = []
    for ev in await audit_service.list_recent(session, limit=100):
        actor = await user_repo.get_by_id(session, ev.actor_id)
        out.append(
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
    return out
