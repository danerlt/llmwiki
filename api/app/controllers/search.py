import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.wiki import PageOut
from app.services import retrieval_service

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[PageOut])
async def search(
    q: str = Query(...),
    kb: list[uuid.UUID] | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await retrieval_service.retrieve(session, user, q, kb_scope=kb)
