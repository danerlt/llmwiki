from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import require_admin
from app.db.session import get_db
from app.schemas.analytics import AnalyticsOut, ReindexResult
from app.services import analytics_service

router = APIRouter(tags=["analytics"], dependencies=[Depends(require_admin)])


@router.get("/analytics", response_model=Response[AnalyticsOut])
@api_response
async def analytics(
    stale_days: int = Query(90, ge=1, le=3650),
    session: AsyncSession = Depends(get_db),
):
    """管理员分析：问答满意度 + 内容健康（陈旧页/孤儿页/待复审）+ 知识空缺。"""
    return await analytics_service.overview(session, stale_days)


@router.post("/admin/embeddings/reindex", response_model=Response[ReindexResult])
@api_response
async def reindex_embeddings(session: AsyncSession = Depends(get_db)):
    """为所有内容页重建语义向量（admin）。embeddings 未启用时为空操作。"""
    return await analytics_service.reindex_embeddings(session)
