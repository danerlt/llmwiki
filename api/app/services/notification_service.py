import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ForbiddenException, NotFoundException
from app.models import User, WikiPage
from app.repositories import notification_repo, subscription_repo, wiki_repo
from app.schemas.notification import NotificationOut, UnreadCount
from app.services.permission_service import permission_service


class NotificationService:
    """订阅与站内通知。"""

    async def _readable_page(
        self, session: AsyncSession, page_id: uuid.UUID, user: User
    ) -> WikiPage:
        page = await wiki_repo.get_by_id(session, page_id)
        if page is None:
            raise NotFoundException("page not found")
        if page.kb_id not in await permission_service.accessible_kb_ids(session, user):
            raise ForbiddenException("no access")
        return page

    async def notify_watchers(
        self,
        session: AsyncSession,
        *,
        page_id: uuid.UUID,
        actor_id: uuid.UUID,
        type: str,
        message: str,
    ) -> None:
        """给关注该页的用户（排除操作者本人）各发一条通知。不 commit，随业务事务提交。"""
        for uid in await subscription_repo.subscriber_ids(session, page_id):
            if uid == actor_id:
                continue
            await notification_repo.create(
                session, user_id=uid, type=type, message=message, page_id=page_id, actor_id=actor_id
            )

    async def subscribe(self, session: AsyncSession, user: User, page_id: uuid.UUID) -> None:
        await self._readable_page(session, page_id, user)
        await subscription_repo.add(session, user_id=user.id, page_id=page_id)
        await session.commit()

    async def unsubscribe(self, session: AsyncSession, user: User, page_id: uuid.UUID) -> None:
        await subscription_repo.remove(session, user_id=user.id, page_id=page_id)
        await session.commit()

    async def list_notifications(self, session: AsyncSession, user: User) -> list[NotificationOut]:
        rows = await notification_repo.list_for(session, user.id)
        return [NotificationOut.model_validate(r) for r in rows]

    async def unread_count(self, session: AsyncSession, user_id: uuid.UUID) -> UnreadCount:
        return UnreadCount(count=await notification_repo.unread_count(session, user_id))

    async def mark_all_read(self, session: AsyncSession, user: User) -> None:
        await notification_repo.mark_all_read(session, user.id)
        await session.commit()


notification_service = NotificationService()
