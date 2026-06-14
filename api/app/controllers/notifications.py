import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.notification import NotificationOut, UnreadCount
from app.services import notification_service

router = APIRouter(tags=["notifications"])


@router.post("/pages/{page_id}/subscribe", status_code=status.HTTP_204_NO_CONTENT)
@api_response
async def subscribe(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await notification_service.subscribe(session, user, page_id)


@router.delete("/pages/{page_id}/subscribe", status_code=status.HTTP_204_NO_CONTENT)
@api_response
async def unsubscribe(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await notification_service.unsubscribe(session, user, page_id)


@router.get("/notifications", response_model=Response[list[NotificationOut]])
@api_response
async def my_notifications(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await notification_service.list_notifications(session, user)


@router.get("/notifications/unread-count", response_model=Response[UnreadCount])
@api_response
async def unread_count(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await notification_service.unread_count(session, user.id)


@router.post("/notifications/read", status_code=status.HTTP_204_NO_CONTENT)
@api_response
async def mark_all_read(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await notification_service.mark_all_read(session, user)
