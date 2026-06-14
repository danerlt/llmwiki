from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import source_repo, wiki_repo
from app.schemas.wiki import StatsOut
from app.services import permission_service, promotion_service

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=Response[StatsOut])
@api_response
async def stats(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    ids = list(await permission_service.accessible_kb_ids(session, user))
    counts = await wiki_repo.counts_by_kbs(session, ids)
    source_count = await source_repo.count_by_kbs(session, ids)
    pending = len(await promotion_service.list_reviewable(session, user))
    return StatsOut(
        kb_count=len(ids),
        page_count=sum(counts.values()),
        source_count=source_count,
        pending_reviews=pending,
    )
