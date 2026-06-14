import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response as FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.integrations.storage import MinioStorage, StorageBackend
from app.models import User
from app.schemas.source import SourceCreatedOut, SourceOut
from app.services.source_service import source_service

router = APIRouter(tags=["sources"])


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
    return await source_service.upload(session, user, kb_id, file, storage)


@router.get("/kbs/{kb_id}/sources", response_model=Response[list[SourceOut]])
@api_response
async def list_sources(
    kb_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await source_service.list_by_kb(session, user, kb_id)


@router.get("/sources/{source_id}", response_model=Response[SourceOut])
@api_response
async def get_source(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await source_service.get(session, user, source_id)


@router.post("/sources/{source_id}/reingest", response_model=Response[SourceOut])
@api_response
async def reingest_source(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await source_service.reingest(session, user, source_id)


@router.get("/sources/{source_id}/download")
async def download_source(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    """查看/下载源的原始上传文件（读权限）。inline 让浏览器尽量内联预览(md/pdf/txt)。"""
    data, filename, content_type = await source_service.get_file(session, user, source_id, storage)
    return FileResponse(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}"},
    )
