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
    limit: int = 8,
) -> list[WikiPage]:
    """权限感知检索：关键词召回 → page_links/共享源图扩展 → 截断到 limit → 附 index 目录。
    铁律：返回集合中每页 kb_id 必属 accessible_kb_ids(user)。
    内容页按 种子(关键词) > 链接 > 共享源 优先级排序并 cap 到 limit，避免单源 KB 下一次召回过多。"""
    kb_ids = await permission_service.accessible_kb_ids(session, user)
    if kb_scope is not None:
        kb_ids = kb_ids & set(kb_scope)
    if not kb_ids:
        return []
    kb_id_list = list(kb_ids)

    seeds = await wiki_repo.search_pages(session, kb_id_list, q, limit=limit)
    result: dict[uuid.UUID, WikiPage] = {p.id: p for p in seeds}

    # 图扩展 1：page_links 直接链接（高信号，已回填 to_page_id）
    for p in await wiki_repo.linked_pages(session, list(result.keys())):
        if p.kb_id in kb_ids:  # 权限再过滤
            result.setdefault(p.id, p)

    # 图扩展 2：共享 source_ids 噪声大（同源页极多），仅在未达 limit 时补，且补满即停
    if len(result) < limit:
        seed_sources = {sid for p in seeds for sid in (p.source_ids or [])}
        if seed_sources:
            for p in await wiki_repo.list_by_kbs(session, kb_id_list):
                if len(result) >= limit:
                    break
                if seed_sources & set(p.source_ids or []):
                    result.setdefault(p.id, p)

    # 内容页截断到 limit（dict 保序：种子 > 链接 > 共享源）
    pages = list(result.values())[:limit]

    # 附各涉及 KB 的 index 目录页作为“地图”（不计入 limit）
    chosen = {p.id for p in pages}
    for kb_id in {p.kb_id for p in pages}:
        idx = await wiki_repo.get_by_slug(session, kb_id, "index")
        if idx is not None and idx.kb_id in kb_ids and idx.id not in chosen:
            pages.append(idx)
            chosen.add(idx.id)
    return pages
