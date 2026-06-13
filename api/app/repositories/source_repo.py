import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source


async def create(
    session: AsyncSession,
    *,
    kb_id: uuid.UUID,
    uploader_id: uuid.UUID,
    filename: str,
    content_type: str,
    storage_key: str,
    status: str = "pending",
) -> Source:
    src = Source(
        kb_id=kb_id,
        uploader_id=uploader_id,
        filename=filename,
        content_type=content_type,
        storage_key=storage_key,
        status=status,
    )
    session.add(src)
    return src


async def get_by_id(session: AsyncSession, source_id: uuid.UUID) -> Source | None:
    res = await session.execute(select(Source).where(Source.id == source_id))
    return res.scalar_one_or_none()


async def set_status(
    session: AsyncSession, source_id: uuid.UUID, status: str, error: str | None = None
) -> None:
    src = await get_by_id(session, source_id)
    if src is not None:
        src.status = status
        src.error = error


async def set_job_id(session: AsyncSession, source_id: uuid.UUID, job_id: str) -> None:
    src = await get_by_id(session, source_id)
    if src is not None:
        src.job_id = job_id


async def list_by_kb(session: AsyncSession, kb_id: uuid.UUID) -> list[Source]:
    res = await session.execute(select(Source).where(Source.kb_id == kb_id))
    return list(res.scalars().all())
