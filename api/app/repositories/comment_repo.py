import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Comment


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


async def delete(session: AsyncSession, comment_id: uuid.UUID) -> None:
    c = await get_by_id(session, comment_id)
    if c is not None:
        await session.delete(c)
