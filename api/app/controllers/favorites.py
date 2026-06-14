import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.wiki import PageOut
from app.services.favorite_service import favorite_service

router = APIRouter(tags=["favorites"])


@router.get("/favorites", response_model=Response[list[PageOut]])
@api_response
async def my_favorites(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await favorite_service.list_favorites(session, user)


@router.post("/pages/{page_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
@api_response
async def add_favorite(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await favorite_service.add_favorite(session, user, page_id)


@router.delete("/pages/{page_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
@api_response
async def remove_favorite(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await favorite_service.remove_favorite(session, user, page_id)
