import uuid

from sqlalchemy import func, select, update
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


async def claim(session: AsyncSession, source_id: uuid.UUID) -> bool:
    """原子认领：把非 processing 的源置为 processing 并清空错误；已在 processing 则返回 False。

    依赖 UPDATE ... WHERE status != 'processing' 的行级锁实现并发去重——
    两个 job 同时认领同一 source 时，后者会阻塞至前者提交，再因条件不满足而认领失败，
    避免双写同一 (kb_id, slug) 触发唯一约束冲突。
    """
    res = await session.execute(
        update(Source)
        .where(Source.id == source_id, Source.status != "processing")
        .values(status="processing", error=None)
    )
    return (res.rowcount or 0) > 0


async def set_job_id(session: AsyncSession, source_id: uuid.UUID, job_id: str) -> None:
    src = await get_by_id(session, source_id)
    if src is not None:
        src.job_id = job_id


async def list_by_kb(session: AsyncSession, kb_id: uuid.UUID) -> list[Source]:
    res = await session.execute(select(Source).where(Source.kb_id == kb_id))
    return list(res.scalars().all())


async def list_by_ids(session: AsyncSession, ids: list[uuid.UUID]) -> list[Source]:
    if not ids:
        return []
    res = await session.execute(select(Source).where(Source.id.in_(ids)))
    return list(res.scalars().all())


async def count_by_kbs(session: AsyncSession, kb_ids: list[uuid.UUID]) -> int:
    if not kb_ids:
        return 0
    res = await session.execute(
        select(func.count()).select_from(Source).where(Source.kb_id.in_(kb_ids))
    )
    return int(res.scalar() or 0)
