import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, WikiPage
from app.repositories import wiki_repo
from app.services import permission_service


async def retrieve(
    session: AsyncSession,
    user: User,
    q: str,
    kb_scope: list[uuid.UUID] | None = None,
    limit: int = 10,
) -> list[WikiPage]:
    """权限感知检索：关键词召回 → page_links/共享源图扩展 → 附 index 目录。
    铁律：返回集合中每页 kb_id 必属 accessible_kb_ids(user)。"""
    kb_ids = await permission_service.accessible_kb_ids(session, user)
    if kb_scope is not None:
        kb_ids = kb_ids & set(kb_scope)
    if not kb_ids:
        return []
    kb_id_list = list(kb_ids)

    seeds = await wiki_repo.search_pages(session, kb_id_list, q, limit=limit)
    result: dict[uuid.UUID, WikiPage] = {p.id: p for p in seeds}

    # 图扩展 1：page_links 直接链接（已回填 to_page_id）
    linked = await wiki_repo.linked_pages(session, list(result.keys()))
    for p in linked:
        if p.kb_id in kb_ids:  # 权限再过滤
            result.setdefault(p.id, p)

    # 图扩展 2：共享 source_ids（Python 交集）
    seed_sources = {sid for p in seeds for sid in (p.source_ids or [])}
    if seed_sources:
        for p in await wiki_repo.list_by_kbs(session, kb_id_list):
            if seed_sources & set(p.source_ids or []):
                result.setdefault(p.id, p)

    # 附上涉及 KB 的 index 目录页
    for kb_id in {p.kb_id for p in result.values()}:
        idx = await wiki_repo.get_by_slug(session, kb_id, "index")
        if idx is not None and idx.kb_id in kb_ids:
            result.setdefault(idx.id, idx)

    return list(result.values())
