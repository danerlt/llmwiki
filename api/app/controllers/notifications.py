import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import notification_repo, subscription_repo, wiki_repo
from app.schemas.notification import NotificationOut
from app.services import permission_service

router = APIRouter(tags=["notifications"])


async def _readable_page(session: AsyncSession, page_id: uuid.UUID, user: User):
    page = await wiki_repo.get_by_id(session, page_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page not found")
    accessible = await permission_service.accessible_kb_ids(session, user)
    if page.kb_id not in accessible:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no access")
    return page


@router.post("/pages/{page_id}/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await _readable_page(session, page_id, user)
    await subscription_repo.add(session, user_id=user.id, page_id=page_id)
    await session.commit()


@router.delete("/pages/{page_id}/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await subscription_repo.remove(session, user_id=user.id, page_id=page_id)
    await session.commit()


@router.get("/notifications", response_model=list[NotificationOut])
async def my_notifications(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await notification_repo.list_for(session, user.id)


@router.get("/notifications/unread-count")
async def unread_count(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return {"count": await notification_repo.unread_count(session, user.id)}


@router.post("/notifications/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await notification_repo.mark_all_read(session, user.id)
    await session.commit()
