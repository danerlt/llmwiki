from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_db
from app.repositories import feedback_repo, wiki_repo

router = APIRouter(tags=["analytics"], dependencies=[Depends(require_admin)])


def _page_brief(p) -> dict:
    return {
        "id": str(p.id),
        "kb_id": str(p.kb_id),
        "title": p.title,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/analytics")
async def analytics(
    stale_days: int = Query(90, ge=1, le=3650),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """管理员分析：问答满意度 + 内容健康（陈旧页 / 孤儿页）。"""
    before = datetime.now(timezone.utc) - timedelta(days=stale_days)
    fb = await feedback_repo.counts(session)
    stale = await wiki_repo.stale_pages(session, before, limit=50)
    orphan = await wiki_repo.orphan_pages(session, limit=50)
    review_due = await wiki_repo.review_due_pages(session, before, limit=50)
    return {
        "feedback": {"up": fb.get("up", 0), "down": fb.get("down", 0)},
        "stale_days": stale_days,
        "stale_pages": [_page_brief(p) for p in stale],
        "orphan_pages": [_page_brief(p) for p in orphan],
        "review_due_pages": [_page_brief(p) for p in review_due],
    }
