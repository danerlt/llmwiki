import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.wiki import SearchHit
from app.services import retrieval_service

router = APIRouter(tags=["search"])


@router.get("/search", response_model=Response[list[SearchHit]])
@api_response
async def search(
    q: str = Query(..., min_length=1, max_length=500),
    kb: list[uuid.UUID] | None = Query(default=None),
    page_type: str | None = Query(default=None, description="按页类型过滤"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await retrieval_service.search(session, user, q, kb, page_type)
