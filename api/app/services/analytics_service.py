from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WikiPage
from app.repositories import feedback_repo, search_miss_repo, wiki_repo
from app.schemas.analytics import (
    AnalyticsOut,
    FeedbackCount,
    PageBrief,
    ReindexResult,
    SearchMissItem,
)
from app.services.embedding_service import embedding_service


class AnalyticsService:
    """管理员分析：问答满意度、内容健康（陈旧/孤儿/待复审）、知识空缺、向量重建。"""

    def _brief(self, p: WikiPage) -> PageBrief:
        return PageBrief(
            id=str(p.id),
            kb_id=str(p.kb_id),
            title=p.title,
            updated_at=p.updated_at.isoformat() if p.updated_at else None,
        )

    async def overview(self, session: AsyncSession, stale_days: int) -> AnalyticsOut:
        before = datetime.now(timezone.utc) - timedelta(days=stale_days)
        fb = await feedback_repo.counts(session)
        stale = await wiki_repo.stale_pages(session, before, limit=50)
        orphan = await wiki_repo.orphan_pages(session, limit=50)
        review_due = await wiki_repo.review_due_pages(session, before, limit=50)
        misses = await search_miss_repo.top(session, limit=50)
        return AnalyticsOut(
            feedback=FeedbackCount(up=fb.get("up", 0), down=fb.get("down", 0)),
            stale_days=stale_days,
            stale_pages=[self._brief(p) for p in stale],
            orphan_pages=[self._brief(p) for p in orphan],
            review_due_pages=[self._brief(p) for p in review_due],
            search_misses=[
                SearchMissItem(query=q, count=c, last_seen=ls.isoformat() if ls else None)
                for q, c, ls in misses
            ],
        )

    async def reindex_embeddings(self, session: AsyncSession) -> ReindexResult:
        """为所有内容页重建语义向量。embeddings 未启用时为空操作。"""
        if not embedding_service.enabled():
            return ReindexResult(enabled=False, reindexed=0)
        n = 0
        for p in await wiki_repo.all_content_pages(session):
            vec = embedding_service.embed(f"{p.title}\n{p.content_md or ''}")
            if vec is not None:
                p.embedding = vec
                n += 1
        await session.commit()
        return ReindexResult(enabled=True, reindexed=n)


analytics_service = AnalyticsService()
