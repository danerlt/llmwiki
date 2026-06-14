import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SearchMiss


async def record(session: AsyncSession, *, user_id: uuid.UUID, query: str) -> SearchMiss:
    miss = SearchMiss(user_id=user_id, query=query)
    session.add(miss)
    return miss


async def top(session: AsyncSession, *, limit: int = 50) -> list[tuple[str, int, datetime]]:
    """按 query 聚合无果词，返回 [(query, count, last_seen)]，按次数降序。供知识空缺看板。"""
    res = await session.execute(
        select(SearchMiss.query, func.count(), func.max(SearchMiss.created_at))
        .group_by(SearchMiss.query)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return [(row[0], int(row[1]), row[2]) for row in res.all()]
