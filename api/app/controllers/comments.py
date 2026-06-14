import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.comment import CommentCreate, CommentOut
from app.services.comment_service import comment_service

router = APIRouter(tags=["comments"])


@router.get("/pages/{page_id}/comments", response_model=Response[list[CommentOut]])
@api_response
async def list_comments(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await comment_service.list_comments(session, user, page_id)


@router.post("/pages/{page_id}/comments", response_model=Response[CommentOut], status_code=status.HTTP_201_CREATED)
@api_response
async def add_comment(
    page_id: uuid.UUID,
    body: CommentCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await comment_service.add_comment(session, user, page_id, body)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
@api_response
async def delete_comment(
    comment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await comment_service.delete_comment(session, user, comment_id)
