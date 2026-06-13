import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, WikiPage
from app.repositories import wiki_repo
from app.services import permission_service

_ASCII_RE = re.compile(r"[A-Za-z0-9]+")
_CJK_RE = re.compile(r"[一-鿿]+")
# 常见无信息量的中文单字（无分词器时减少噪声）
_STOP = set("的了是有哪些么什怎如和与吗呢在对为及或请问个这那你我他它将被把")


def _query_terms(q: str) -> list[str]:
    """把查询切成检索词：ASCII 词（>=2）+ 中文相邻二元组（无分词器时的中文召回兜底）。
    自然语言整句不再当作单一子串，从而能召回相关页。"""
    terms: list[str] = []
    seen: set[str] = set()

    def add(t: str) -> None:
        if t and t not in seen:
            seen.add(t)
            terms.append(t)

    for m in _ASCII_RE.findall(q.lower()):
        if len(m) >= 2:
            add(m)
    for run in _CJK_RE.findall(q):
        if len(run) == 1:
            if run not in _STOP:
                add(run)
        else:
            for i in range(len(run) - 1):
                add(run[i : i + 2])
    return terms


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

    # 按词召回：每个检索词各查一次，按命中词数排序（多词命中=更相关）
    terms = _query_terms(q)
    if not terms:
        seeds = await wiki_repo.search_pages(session, kb_id_list, q, limit=limit)
    else:
        scored: dict[uuid.UUID, list] = {}
        for t in terms:
            for p in await wiki_repo.search_pages(session, kb_id_list, t, limit=limit * 3):
                entry = scored.setdefault(p.id, [p, 0])
                entry[1] += 1
        seeds = [pair[0] for pair in sorted(scored.values(), key=lambda x: -x[1])][:limit]
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
