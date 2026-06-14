import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import notification_repo, subscription_repo


async def notify_watchers(
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
