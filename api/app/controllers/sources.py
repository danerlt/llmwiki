import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.exceptions import (
    ForbiddenException,
    NotFoundException,
    ParamsException,
)
from app.common.response import Response
from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.integrations.storage import MinioStorage, StorageBackend
from app.models import User
from app.repositories import kb_repo, source_repo
from app.schemas.source import SourceCreatedOut, SourceOut
from app.services import audit_service, permission_service
from app.worker.queue import enqueue_ingest

router = APIRouter(tags=["sources"])

_ALLOWED_EXTS = (".md", ".txt", ".pdf", ".docx", ".html", ".htm")


async def _enqueue_or_fail(session: AsyncSession, source_id: uuid.UUID) -> None:
    """入队成功则回写 job_id；失败（如 Redis 不可用）则把源置 failed 并返回 503——
    避免源在‘先提交 pending 再入队’模式下因入队异常永久卡在 pending（系统无后台清扫器）。"""
    try:
        job_id = await enqueue_ingest(str(source_id))
    except Exception:  # noqa: BLE001 — 任何入队故障都不能让源静默卡死
        await source_repo.set_status(session, source_id, "failed", error="enqueue_failed")
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="任务队列暂不可用，请稍后重试"
        )
    await source_repo.set_job_id(session, source_id, job_id)
    await session.commit()


def get_storage() -> StorageBackend:
    return MinioStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket_sources,
        secure=settings.minio_secure,
    )


@router.post("/kbs/{kb_id}/sources", response_model=Response[SourceCreatedOut])
@api_response
async def upload_source(
    kb_id: uuid.UUID,
    file: UploadFile,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    kb = await kb_repo.get_by_id(session, kb_id)
    if kb is None:
        raise NotFoundException("kb not found")
    if not await permission_service.can_write(session, user, kb):
        raise ForbiddenException("no write permission")

    filename = file.filename or "upload.bin"
    if not any(filename.lower().endswith(ext) for ext in _ALLOWED_EXTS):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="仅支持 .md/.txt/.pdf/.docx/.html",
        )
    # 分块读取并随读随校验大小：超限立即中止，避免把超大请求体整体读入内存/临时盘（DoS）
    buf = bytearray()
    while chunk := await file.read(1024 * 1024):
        buf.extend(chunk)
        if len(buf) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file too large"
            )
    data = bytes(buf)
    if not data:
        raise ParamsException("empty file")
    src = await source_repo.create(
        session,
        kb_id=kb_id,
        uploader_id=user.id,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        storage_key="",  # 落库拿到 id 后再定 key
    )
    await session.flush()
    storage_key = f"{kb_id}/{src.id}/{src.filename}"
    storage.put(storage_key, data, src.content_type)
    src.storage_key = storage_key
    await audit_service.record(
        session, actor_id=user.id, action="source.upload",
        target_type="source", target_id=src.id,
        detail={"kb_id": str(kb_id), "filename": src.filename},
    )
    # 先持久化 source（worker 出队时必可见），再入队，消除“提交前入队”竞态
    await session.commit()
    await _enqueue_or_fail(session, src.id)
    return SourceCreatedOut(source_id=src.id, status="pending")


@router.get("/kbs/{kb_id}/sources", response_model=Response[list[SourceOut]])
@api_response
async def list_sources(
    kb_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    accessible = await permission_service.accessible_kb_ids(session, user)
    if kb_id not in accessible:
        raise ForbiddenException("no access")
    return await source_repo.list_by_kb(session, kb_id)


@router.get("/sources/{source_id}", response_model=Response[SourceOut])
@api_response
async def get_source(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    src = await source_repo.get_by_id(session, source_id)
    if src is None:
        raise NotFoundException("source not found")
    accessible = await permission_service.accessible_kb_ids(session, user)
    if src.kb_id not in accessible:
        raise ForbiddenException("no access")
    return src


@router.post("/sources/{source_id}/reingest", response_model=Response[SourceOut])
@api_response
async def reingest_source(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    src = await source_repo.get_by_id(session, source_id)
    if src is None:
        raise NotFoundException("source not found")
    kb = await kb_repo.get_by_id(session, src.kb_id)
    if kb is None or not await permission_service.can_write(session, user, kb):
        raise ForbiddenException("no write permission")
    # 复位状态再入队：失败/已完成的源都可重新摄入一遍
    await source_repo.set_status(session, source_id, "pending", error=None)
    await audit_service.record(
        session, actor_id=user.id, action="source.reingest",
        target_type="source", target_id=source_id,
        detail={"kb_id": str(src.kb_id), "filename": src.filename},
    )
    await session.commit()
    await _enqueue_or_fail(session, source_id)
    return src
