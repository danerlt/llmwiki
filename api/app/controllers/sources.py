import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

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

_ALLOWED_EXTS = (".md", ".txt", ".pdf")


def get_storage() -> StorageBackend:
    return MinioStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket_sources,
        secure=settings.minio_secure,
    )


@router.post("/kbs/{kb_id}/sources", response_model=SourceCreatedOut)
async def upload_source(
    kb_id: uuid.UUID,
    file: UploadFile,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    kb = await kb_repo.get_by_id(session, kb_id)
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="kb not found")
    if not await permission_service.can_write(session, user, kb):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no write permission")

    filename = file.filename or "upload.bin"
    if not any(filename.lower().endswith(ext) for ext in _ALLOWED_EXTS):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="仅支持 .md/.txt/.pdf"
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty file")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file too large"
        )
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

    job_id = await enqueue_ingest(str(src.id))
    await source_repo.set_job_id(session, src.id, job_id)
    await session.commit()
    return SourceCreatedOut(source_id=src.id, status=src.status)


@router.get("/sources/{source_id}", response_model=SourceOut)
async def get_source(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    src = await source_repo.get_by_id(session, source_id)
    if src is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    accessible = await permission_service.accessible_kb_ids(session, user)
    if src.kb_id not in accessible:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no access")
    return src
