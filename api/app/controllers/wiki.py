import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import source_repo, wiki_repo
from app.schemas.wiki import PageDetailOut, PageOut, SourceRef
from app.services import permission_service

router = APIRouter(tags=["wiki"])


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

    backlinks = [b for b in await wiki_repo.backlinks(session, page_id) if b.kb_id in accessible]
    src_ids: list[uuid.UUID] = []
    for s in page.source_ids or []:
        try:
            src_ids.append(uuid.UUID(str(s)))
        except (ValueError, TypeError):
            pass
    sources = await source_repo.list_by_ids(session, src_ids)

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
        sources=[SourceRef(id=s.id, filename=s.filename) for s in sources],
    )
