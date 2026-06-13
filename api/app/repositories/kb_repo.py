import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase


async def create(
    session: AsyncSession, *, scope_type: str, scope_ref_id: uuid.UUID | None, name: str
) -> KnowledgeBase:
    kb = KnowledgeBase(scope_type=scope_type, scope_ref_id=scope_ref_id, name=name)
    session.add(kb)
    return kb


async def list_by_scope(
    session: AsyncSession, scope_type: str, scope_ref_id: uuid.UUID | None
) -> list[KnowledgeBase]:
    stmt = select(KnowledgeBase).where(KnowledgeBase.scope_type == scope_type)
    stmt = stmt.where(
        KnowledgeBase.scope_ref_id == scope_ref_id
        if scope_ref_id is not None
        else KnowledgeBase.scope_ref_id.is_(None)
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def list_by_ids(session: AsyncSession, ids: list[uuid.UUID]) -> list[KnowledgeBase]:
    if not ids:
        return []
    res = await session.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(ids)))
    return list(res.scalars().all())
