import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Comment, WikiPage


async def create(
    session: AsyncSession, *, page_id: uuid.UUID, author_id: uuid.UUID, body: str
) -> Comment:
    c = Comment(page_id=page_id, author_id=author_id, body=body)
    session.add(c)
    return c


async def get_by_id(session: AsyncSession, comment_id: uuid.UUID) -> Comment | None:
    res = await session.execute(select(Comment).where(Comment.id == comment_id))
    return res.scalar_one_or_none()


async def list_by_author(session: AsyncSession, author_id: uuid.UUID) -> list[Comment]:
    res = await session.execute(
        select(Comment).where(Comment.author_id == author_id).order_by(Comment.created_at)
    )
    return list(res.scalars().all())


async def list_by_page(session: AsyncSession, page_id: uuid.UUID) -> list[Comment]:
    res = await session.execute(
        select(Comment).where(Comment.page_id == page_id).order_by(Comment.created_at)
    )
    return list(res.scalars().all())


async def recent_in_kbs(
    session: AsyncSession, kb_ids: list[uuid.UUID], limit: int = 20
) -> list[tuple[Comment, WikiPage]]:
    """可见 KB 内最近评论（连同所属页），用于活动流。"""
    if not kb_ids:
        return []
    res = await session.execute(
        select(Comment, WikiPage)
        .join(WikiPage, Comment.page_id == WikiPage.id)
        .where(WikiPage.kb_id.in_(kb_ids))
        .order_by(desc(Comment.created_at))
        .limit(limit)
    )
    return [(row[0], row[1]) for row in res.all()]


async def delete(session: AsyncSession, comment_id: uuid.UUID) -> None:
    c = await get_by_id(session, comment_id)
    if c is not None:
        await session.delete(c)
