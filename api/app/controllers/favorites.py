import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.exceptions import ForbiddenException, NotFoundException
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import favorite_repo, wiki_repo
from app.schemas.wiki import PageOut
from app.services import permission_service

router = APIRouter(tags=["favorites"])


async def _readable_page(session: AsyncSession, page_id: uuid.UUID, user: User):
    page = await wiki_repo.get_by_id(session, page_id)
    if page is None:
        raise NotFoundException("page not found")
    accessible = await permission_service.accessible_kb_ids(session, user)
    if page.kb_id not in accessible:
        raise ForbiddenException("no access")
    return page


@router.get("/favorites", response_model=Response[list[PageOut]])
@api_response
async def my_favorites(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    accessible = await permission_service.accessible_kb_ids(session, user)
    # 仅返回当前仍可见的收藏页（作用域可能已变化）
    return [p for p in await favorite_repo.list_pages(session, user.id) if p.kb_id in accessible]


@router.post("/pages/{page_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
@api_response
async def add_favorite(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await _readable_page(session, page_id, user)
    await favorite_repo.add(session, user_id=user.id, page_id=page_id)
    await session.commit()


@router.delete("/pages/{page_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
@api_response
async def remove_favorite(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await favorite_repo.remove(session, user_id=user.id, page_id=page_id)
    await session.commit()
