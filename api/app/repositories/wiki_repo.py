import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PageLink, WikiPage


async def get_by_slug(session: AsyncSession, kb_id: uuid.UUID, slug: str) -> WikiPage | None:
    res = await session.execute(
        select(WikiPage).where(WikiPage.kb_id == kb_id, WikiPage.slug == slug)
    )
    return res.scalar_one_or_none()


async def get_by_id(session: AsyncSession, page_id: uuid.UUID) -> WikiPage | None:
    res = await session.execute(select(WikiPage).where(WikiPage.id == page_id))
    return res.scalar_one_or_none()


async def list_by_kb(session: AsyncSession, kb_id: uuid.UUID) -> list[WikiPage]:
    res = await session.execute(select(WikiPage).where(WikiPage.kb_id == kb_id))
    return list(res.scalars().all())


async def upsert(
    session: AsyncSession,
    *,
    kb_id: uuid.UUID,
    slug: str,
    title: str,
    page_type: str,
    content_md: str,
    frontmatter: dict,
    source_ids: list[str],
) -> WikiPage:
    page = await get_by_slug(session, kb_id, slug)
    if page is None:
        page = WikiPage(kb_id=kb_id, slug=slug)
        session.add(page)
    page.title = title
    page.page_type = page_type
    page.content_md = content_md
    page.frontmatter = frontmatter
    page.source_ids = source_ids
    return page


async def replace_links(
    session: AsyncSession, *, from_page_id: uuid.UUID, to_slugs: list[str]
) -> None:
    await session.execute(delete(PageLink).where(PageLink.from_page_id == from_page_id))
    for slug in dict.fromkeys(to_slugs):  # 去重保序
        session.add(PageLink(from_page_id=from_page_id, to_slug=slug, to_page_id=None))


async def links_from(session: AsyncSession, from_page_id: uuid.UUID) -> list[PageLink]:
    res = await session.execute(
        select(PageLink).where(PageLink.from_page_id == from_page_id)
    )
    return list(res.scalars().all())


async def backfill_link_targets(session: AsyncSession, *, kb_id: uuid.UUID) -> None:
    """把本 KB 内 to_slug 命中既有页 slug 的 page_links 回填 to_page_id。"""
    pages = await list_by_kb(session, kb_id)
    slug_to_id = {p.slug: p.id for p in pages}
    page_ids = list(slug_to_id.values())
    if not page_ids:
        return
    res = await session.execute(
        select(PageLink).where(PageLink.from_page_id.in_(page_ids))
    )
    for link in res.scalars().all():
        link.to_page_id = slug_to_id.get(link.to_slug)
