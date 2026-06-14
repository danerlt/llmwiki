from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories import source_repo, wiki_repo
from app.schemas.wiki import StatsOut
from app.services.permission_service import permission_service
from app.services.promotion_service import promotion_service


class StatsService:
    """聚合当前用户可见范围内的统计概览。"""

    async def overview(self, session: AsyncSession, user: User) -> StatsOut:
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


stats_service = StatsService()
