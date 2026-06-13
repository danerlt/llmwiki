import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase
from app.repositories import kb_repo


async def ensure_kb(
    session: AsyncSession, scope_type: str, scope_ref_id: uuid.UUID | None, name: str
) -> KnowledgeBase:
    existing = await kb_repo.list_by_scope(session, scope_type, scope_ref_id)
    if existing:
        return existing[0]
    return await kb_repo.create(session, scope_type=scope_type, scope_ref_id=scope_ref_id, name=name)
