import uuid

from sqlalchemy import delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Comment,
    Favorite,
    Notification,
    PageLink,
    PageVersion,
    Subscription,
    WikiPage,
)


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


async def delete_page(session: AsyncSession, page_id: uuid.UUID) -> None:
    """删除页及其相关链接（出链与入链）、历史版本与评论，用于 reingest 清理孤儿页与人工删除。"""
    await session.execute(
        delete(PageLink).where(
            or_(PageLink.from_page_id == page_id, PageLink.to_page_id == page_id)
        )
    )
    await session.execute(delete(PageVersion).where(PageVersion.page_id == page_id))
    await session.execute(delete(Comment).where(Comment.page_id == page_id))
    await session.execute(delete(Favorite).where(Favorite.page_id == page_id))
    await session.execute(delete(Subscription).where(Subscription.page_id == page_id))
    await session.execute(delete(Notification).where(Notification.page_id == page_id))
    await session.execute(delete(WikiPage).where(WikiPage.id == page_id))


async def add_version(
    session: AsyncSession, page: WikiPage, edited_by: uuid.UUID | None = None
) -> PageVersion:
    """把页的【当前】状态快照为一个新版本（version_no 按页单调递增）。"""
    res = await session.execute(
        select(func.max(PageVersion.version_no)).where(PageVersion.page_id == page.id)
    )
    nxt = (res.scalar() or 0) + 1
    v = PageVersion(
        page_id=page.id,
        version_no=nxt,
        title=page.title,
        page_type=page.page_type,
        content_md=page.content_md or "",
        edited_by=edited_by,
    )
    session.add(v)
    return v


async def list_versions(session: AsyncSession, page_id: uuid.UUID) -> list[PageVersion]:
    res = await session.execute(
        select(PageVersion)
        .where(PageVersion.page_id == page_id)
        .order_by(desc(PageVersion.version_no))
    )
    return list(res.scalars().all())


async def get_version(
    session: AsyncSession, page_id: uuid.UUID, version_no: int
) -> PageVersion | None:
    res = await session.execute(
        select(PageVersion).where(
            PageVersion.page_id == page_id, PageVersion.version_no == version_no
        )
    )
    return res.scalar_one_or_none()


async def search_pages(
    session: AsyncSession, kb_ids: list[uuid.UUID], q: str, limit: int = 20
) -> list[WikiPage]:
    """可移植关键词召回：标题/正文子串匹配（lower+LIKE），排除 index，标题命中排前。"""
    if not kb_ids or not q:
        return []
    # 转义 LIKE 元字符（先转义反斜杠本身），使含 % _ 的关键词按字面子串匹配
    escaped = q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    title_match = func.lower(WikiPage.title).like(pattern, escape="\\")
    body_match = func.lower(WikiPage.content_md).like(pattern, escape="\\")
    stmt = (
        select(WikiPage)
        .where(
            WikiPage.kb_id.in_(kb_ids),
            WikiPage.page_type != "index",
            or_(title_match, body_match),
        )
        .order_by(title_match.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def linked_pages(
    session: AsyncSession, from_page_ids: list[uuid.UUID]
) -> list[WikiPage]:
    """种子页经 page_links 直接链接、且已回填 to_page_id 的目标页。"""
    if not from_page_ids:
        return []
    stmt = (
        select(WikiPage)
        .join(PageLink, PageLink.to_page_id == WikiPage.id)
        .where(PageLink.from_page_id.in_(from_page_ids), PageLink.to_page_id.is_not(None))
    )
    res = await session.execute(stmt)
    return list(res.scalars().unique().all())


async def list_by_kbs(session: AsyncSession, kb_ids: list[uuid.UUID]) -> list[WikiPage]:
    if not kb_ids:
        return []
    res = await session.execute(select(WikiPage).where(WikiPage.kb_id.in_(kb_ids)))
    return list(res.scalars().all())


async def all_content_pages(session: AsyncSession) -> list[WikiPage]:
    """所有非 index 内容页（用于 embedding 重建）。"""
    res = await session.execute(select(WikiPage).where(WikiPage.page_type != "index"))
    return list(res.scalars().all())


async def counts_by_kbs(
    session: AsyncSession, kb_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """每个 KB 的内容页数（不含 index 目录页）。"""
    if not kb_ids:
        return {}
    res = await session.execute(
        select(WikiPage.kb_id, func.count())
        .where(WikiPage.kb_id.in_(kb_ids), WikiPage.page_type != "index")
        .group_by(WikiPage.kb_id)
    )
    return {row[0]: int(row[1]) for row in res.all()}


async def backlinks(session: AsyncSession, page_id: uuid.UUID) -> list[WikiPage]:
    """反向链接：哪些页通过 [[wikilink]] 指向本页。"""
    res = await session.execute(
        select(WikiPage)
        .join(PageLink, PageLink.from_page_id == WikiPage.id)
        .where(PageLink.to_page_id == page_id)
    )
    return list(res.scalars().unique().all())


async def outlinks(session: AsyncSession, page_id: uuid.UUID) -> list[WikiPage]:
    """出链：本页通过 [[wikilink]] 指向、且已解析到既有页的目标页。"""
    res = await session.execute(
        select(WikiPage)
        .join(PageLink, PageLink.to_page_id == WikiPage.id)
        .where(PageLink.from_page_id == page_id, PageLink.to_page_id.is_not(None))
    )
    return list(res.scalars().unique().all())


async def stale_pages(session: AsyncSession, before, limit: int = 50) -> list[WikiPage]:
    """陈旧页：updated_at 早于阈值的非 index 页（最旧在前）。"""
    res = await session.execute(
        select(WikiPage)
        .where(WikiPage.page_type != "index", WikiPage.updated_at < before)
        .order_by(WikiPage.updated_at)
        .limit(limit)
    )
    return list(res.scalars().all())


async def review_due_pages(session: AsyncSession, before, limit: int = 50) -> list[WikiPage]:
    """认证已超期、需复审的页（verified_at 早于阈值）。"""
    res = await session.execute(
        select(WikiPage)
        .where(WikiPage.verified_at.is_not(None), WikiPage.verified_at < before)
        .order_by(WikiPage.verified_at)
        .limit(limit)
    )
    return list(res.scalars().all())


async def orphan_pages(session: AsyncSession, limit: int = 50) -> list[WikiPage]:
    """孤儿页：既无出链也无入链的非 index 页（知识孤岛，难被发现）。"""
    from_ids = select(PageLink.from_page_id)
    to_ids = select(PageLink.to_page_id).where(PageLink.to_page_id.is_not(None))
    res = await session.execute(
        select(WikiPage)
        .where(
            WikiPage.page_type != "index",
            WikiPage.id.not_in(from_ids),
            WikiPage.id.not_in(to_ids),
        )
        .limit(limit)
    )
    return list(res.scalars().all())


async def recent(
    session: AsyncSession, kb_ids: list[uuid.UUID], limit: int = 8
) -> list[WikiPage]:
    """跨可见 KB 的最近更新内容页（不含 index）。"""
    if not kb_ids:
        return []
    res = await session.execute(
        select(WikiPage)
        .where(WikiPage.kb_id.in_(kb_ids), WikiPage.page_type != "index")
        .order_by(desc(WikiPage.updated_at))
        .limit(limit)
    )
    return list(res.scalars().all())
