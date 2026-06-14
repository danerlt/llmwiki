import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import require_admin
from app.db.session import get_db
from app.schemas.audit import AuditEventOut
from app.schemas.common import Paginated
from app.services import audit_service

router = APIRouter(tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("/audit", response_model=Response[Paginated[AuditEventOut]])
@api_response
async def list_audit(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None, description="按动作精确过滤，如 page.create"),
    session: AsyncSession = Depends(get_db),
) -> Paginated[AuditEventOut]:
    return await audit_service.list_events(session, limit=limit, offset=offset, action=action)


@router.get("/audit/export")
async def export_audit(
    action: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """导出审计日志为 CSV（合规留证）。"""
    rows = await audit_service.export_rows(session, action=action)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["created_at", "actor_email", "action", "target_type", "target_id", "detail"])
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )
