import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response as RawResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.wiki import (
    PageCreate,
    PageDetailOut,
    PageOut,
    PageUpdate,
    PageVersionOut,
)
from app.services.wiki_service import wiki_service

router = APIRouter(tags=["wiki"])


@router.get("/kbs/{kb_id}/pages", response_model=Response[list[PageOut]])
@api_response
async def list_pages(
    kb_id: uuid.UUID,
    tag: str | None = Query(None, description="按标签过滤"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await wiki_service.list_pages(session, user, kb_id, tag)


@router.post(
    "/kbs/{kb_id}/pages",
    response_model=Response[PageDetailOut],
    status_code=status.HTTP_201_CREATED,
)
@api_response
async def create_page(
    kb_id: uuid.UUID,
    body: PageCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await wiki_service.create_page(session, user, kb_id, body)


@router.put("/pages/{page_id}", response_model=Response[PageDetailOut])
@api_response
async def update_page(
    page_id: uuid.UUID,
    body: PageUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await wiki_service.update_page(session, user, page_id, body)


@router.delete("/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
@api_response
async def delete_page(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await wiki_service.delete_page(session, user, page_id)


@router.get("/pages/{page_id}/versions", response_model=Response[list[PageVersionOut]])
@api_response
async def list_page_versions(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await wiki_service.list_versions(session, user, page_id)


@router.post("/pages/{page_id}/revert/{version_no}", response_model=Response[PageDetailOut])
@api_response
async def revert_page(
    page_id: uuid.UUID,
    version_no: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await wiki_service.revert_page(session, user, page_id, version_no)


@router.get("/pages/{page_id}/markdown")
async def export_page_markdown(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RawResponse:
    """导出页面为 Markdown 文件（含 frontmatter 标题）。需读权限。"""
    body, slug = await wiki_service.export_markdown(session, user, page_id)
    # 文件名可能含非 ASCII：ASCII 兜底 + RFC 5987 filename* 提供 UTF-8 原名
    ascii_name = slug.encode("ascii", "ignore").decode() or "page"
    disp = f"attachment; filename=\"{ascii_name}.md\"; filename*=UTF-8''{quote(slug)}.md"
    return RawResponse(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": disp},
    )


@router.post("/pages/{page_id}/verify", response_model=Response[PageDetailOut])
@api_response
async def verify_page(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await wiki_service.verify_page(session, user, page_id)


@router.delete("/pages/{page_id}/verify", response_model=Response[PageDetailOut])
@api_response
async def unverify_page(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await wiki_service.unverify_page(session, user, page_id)


@router.get("/recent-pages", response_model=Response[list[PageOut]])
@api_response
async def recent_pages(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
):
    return await wiki_service.recent_pages(session, user)


@router.get("/pages/{page_id}", response_model=Response[PageDetailOut])
@api_response
async def get_page(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await wiki_service.get_page(session, user, page_id)
