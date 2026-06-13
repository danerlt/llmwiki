import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.ingest import parser, pipeline
from app.models import User
from app.repositories import kb_repo, source_repo, wiki_repo
from app.schemas.wiki import (
    HUMAN_PAGE_TYPES,
    PageCreate,
    PageDetailOut,
    PageOut,
    PageUpdate,
    PageVersionOut,
    SourceRef,
)
from app.services import audit_service, kb_service, permission_service

router = APIRouter(tags=["wiki"])


async def _build_detail(
    session: AsyncSession, page, accessible: set[uuid.UUID]
) -> PageDetailOut:
    backlinks = [b for b in await wiki_repo.backlinks(session, page.id) if b.kb_id in accessible]
    outlinks = [o for o in await wiki_repo.outlinks(session, page.id) if o.kb_id in accessible]
    src_ids: list[uuid.UUID] = []
    for s in page.source_ids or []:
        try:
            src_ids.append(uuid.UUID(str(s)))
        except (ValueError, TypeError):
            pass
    # 仅返回可见 KB 的来源——晋升等路径可能让页的 source_ids 指向跨作用域的 Source，
    # 与 backlinks/outlinks 的可见性过滤保持一致，避免泄漏他人作用域的源文件名。
    sources = [s for s in await source_repo.list_by_ids(session, src_ids) if s.kb_id in accessible]
    return PageDetailOut(
        id=page.id,
        kb_id=page.kb_id,
        title=page.title,
        slug=page.slug,
        page_type=page.page_type,
        content_md=page.content_md,
        frontmatter=page.frontmatter or {},
        source_ids=[str(s) for s in (page.source_ids or [])],
        updated_at=page.updated_at,
        backlinks=[
            PageOut(id=b.id, kb_id=b.kb_id, title=b.title, slug=b.slug, page_type=b.page_type)
            for b in backlinks
        ],
        outlinks=[
            PageOut(id=o.id, kb_id=o.kb_id, title=o.title, slug=o.slug, page_type=o.page_type)
            for o in outlinks
        ],
        sources=[SourceRef(id=s.id, filename=s.filename) for s in sources],
    )


async def _writable_page(session: AsyncSession, page_id: uuid.UUID, user: User):
    """取页并校验当前用户对其所在 KB 有写权限，否则 404/403。"""
    page = await wiki_repo.get_by_id(session, page_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page not found")
    kb = await kb_repo.get_by_id(session, page.kb_id)
    if kb is None or not await permission_service.can_write(session, user, kb):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no write permission")
    return page


async def _post_write_rebuild(
    session: AsyncSession, page, content_md: str
) -> None:
    """统一的写后处理：刷新链接图 + 重建 index 目录 + 回填 wikilink 目标。"""
    await wiki_repo.replace_links(
        session, from_page_id=page.id, to_slugs=pipeline.extract_wikilinks(content_md or "")
    )
    await session.flush()
    await kb_service.rebuild_index(session, page.kb_id)
    await wiki_repo.backfill_link_targets(session, kb_id=page.kb_id)


@router.get("/kbs/{kb_id}/pages", response_model=list[PageOut])
async def list_pages(
    kb_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    accessible = await permission_service.accessible_kb_ids(session, user)
    if kb_id not in accessible:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no access")
    return await wiki_repo.list_by_kb(session, kb_id)


@router.post("/kbs/{kb_id}/pages", response_model=PageDetailOut, status_code=status.HTTP_201_CREATED)
async def create_page(
    kb_id: uuid.UUID,
    body: PageCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    kb = await kb_repo.get_by_id(session, kb_id)
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="kb not found")
    if not await permission_service.can_write(session, user, kb):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no write permission")
    if body.page_type not in HUMAN_PAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"page_type must be one of {HUMAN_PAGE_TYPES}",
        )
    slug = parser.slugify(body.slug or body.title)
    if not slug:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid slug")
    if await wiki_repo.get_by_slug(session, kb_id, slug) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="slug already exists")
    page = await wiki_repo.upsert(
        session, kb_id=kb_id, slug=slug, title=body.title, page_type=body.page_type,
        content_md=body.content_md, frontmatter={"author": str(user.id)}, source_ids=[],
    )
    await session.flush()
    await wiki_repo.add_version(session, page, edited_by=user.id)  # v1 = 初始内容
    await _post_write_rebuild(session, page, body.content_md)
    await audit_service.record(
        session, actor_id=user.id, action="page.create", target_type="page",
        target_id=page.id, detail={"kb_id": str(kb_id), "slug": slug},
    )
    await session.commit()
    accessible = await permission_service.accessible_kb_ids(session, user)
    return await _build_detail(session, page, accessible)


@router.put("/pages/{page_id}", response_model=PageDetailOut)
async def update_page(
    page_id: uuid.UUID,
    body: PageUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    page = await _writable_page(session, page_id, user)
    if body.page_type is not None and body.page_type not in HUMAN_PAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"page_type must be one of {HUMAN_PAGE_TYPES}",
        )
    if body.title is not None:
        page.title = body.title
    if body.content_md is not None:
        page.content_md = body.content_md
    if body.page_type is not None:
        page.page_type = body.page_type
    await session.flush()
    await wiki_repo.add_version(session, page, edited_by=user.id)  # 每次保存留版本
    await _post_write_rebuild(session, page, page.content_md or "")
    await audit_service.record(
        session, actor_id=user.id, action="page.update", target_type="page",
        target_id=page.id, detail={"kb_id": str(page.kb_id)},
    )
    await session.commit()
    accessible = await permission_service.accessible_kb_ids(session, user)
    return await _build_detail(session, page, accessible)


@router.delete("/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    page = await _writable_page(session, page_id, user)
    if page.page_type == "index":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="cannot delete the index page"
        )
    kb_id = page.kb_id
    await wiki_repo.delete_page(session, page_id)
    await session.flush()
    await kb_service.rebuild_index(session, kb_id)
    await audit_service.record(
        session, actor_id=user.id, action="page.delete", target_type="page",
        target_id=page_id, detail={"kb_id": str(kb_id), "slug": page.slug},
    )
    await session.commit()


@router.get("/pages/{page_id}/versions", response_model=list[PageVersionOut])
async def list_page_versions(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    page = await wiki_repo.get_by_id(session, page_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page not found")
    accessible = await permission_service.accessible_kb_ids(session, user)
    if page.kb_id not in accessible:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no access")
    return await wiki_repo.list_versions(session, page_id)


@router.post("/pages/{page_id}/revert/{version_no}", response_model=PageDetailOut)
async def revert_page(
    page_id: uuid.UUID,
    version_no: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    page = await _writable_page(session, page_id, user)
    target = await wiki_repo.get_version(session, page_id, version_no)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="version not found")
    page.title = target.title
    page.content_md = target.content_md
    page.page_type = target.page_type
    await session.flush()
    await wiki_repo.add_version(session, page, edited_by=user.id)  # 回滚也留痕（新版本）
    await _post_write_rebuild(session, page, page.content_md or "")
    await audit_service.record(
        session, actor_id=user.id, action="page.revert", target_type="page",
        target_id=page.id, detail={"kb_id": str(page.kb_id), "to_version": version_no},
    )
    await session.commit()
    accessible = await permission_service.accessible_kb_ids(session, user)
    return await _build_detail(session, page, accessible)


@router.get("/recent-pages", response_model=list[PageOut])
async def recent_pages(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
):
    ids = await permission_service.accessible_kb_ids(session, user)
    return await wiki_repo.recent(session, list(ids), limit=8)


@router.get("/pages/{page_id}", response_model=PageDetailOut)
async def get_page(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    page = await wiki_repo.get_by_id(session, page_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page not found")
    accessible = await permission_service.accessible_kb_ids(session, user)
    if page.kb_id not in accessible:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no access")
    return await _build_detail(session, page, accessible)
