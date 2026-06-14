import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import search_miss_repo
from app.schemas.wiki import SearchHit
from app.services import retrieval_service
from app.services.retrieval_service import _query_terms, make_snippet

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[SearchHit])
async def search(
    q: str = Query(..., min_length=1, max_length=500),
    kb: list[uuid.UUID] | None = Query(default=None),
    page_type: str | None = Query(default=None, description="按页类型过滤"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    pages = [
        p
        for p in await retrieval_service.retrieve(session, user, q, kb_scope=kb)
        if p.page_type != "index"  # 目录页不进搜索结果
        and (page_type is None or p.page_type == page_type)
    ]
    terms = _query_terms(q)
    hits: list[SearchHit] = []
    for p in pages:
        snippet, matched = make_snippet(p.content_md or "", terms)
        hits.append(
            SearchHit(
                id=p.id,
                kb_id=p.kb_id,
                title=p.title,
                slug=p.slug,
                page_type=p.page_type,
                snippet=snippet,
                matched=matched,
            )
        )
    # 知识空缺：无 page_type 过滤的普通搜索仍 0 结果 → 记录为无果词（过滤导致的空不算）
    if not hits and page_type is None and q.strip():
        await search_miss_repo.record(session, user_id=user.id, query=q.strip())
        await session.commit()
    return hits
