import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingest import parser, pipeline
from app.integrations.storage import StorageBackend
from app.repositories import source_repo, wiki_repo


def _index_markdown(pages) -> str:
    """按 page_type 分组列出非 index 页，生成目录 markdown。"""
    groups: dict[str, list] = {}
    for p in pages:
        if p.page_type == "index":
            continue
        groups.setdefault(p.page_type, []).append(p)
    lines = ["# 目录（index）", ""]
    for ptype in ("overview", "entity", "concept", "source_summary"):
        items = groups.get(ptype)
        if not items:
            continue
        lines.append(f"## {ptype}")
        for p in sorted(items, key=lambda x: x.title):
            lines.append(f"- [[{p.slug}]] {p.title}")
        lines.append("")
    return "\n".join(lines)


async def ingest_source(
    session: AsyncSession,
    source_id: uuid.UUID,
    *,
    llm,
    storage: StorageBackend,
) -> None:
    """确定性两步摄入：解析→分析→生成→落页→链接图→重建 index。失败置 failed。"""
    src = await source_repo.get_by_id(session, source_id)
    if src is None:
        return
    try:
        await source_repo.set_status(session, source_id, "processing")

        data = storage.get(src.storage_key)
        text = parser.parse_to_text(src.filename, src.content_type, data)

        analysis = await pipeline.analyze(llm, text)

        index_page = await wiki_repo.get_by_slug(session, src.kb_id, "index")
        index_md = index_page.content_md if index_page else ""
        drafts = await pipeline.generate_pages(llm, analysis, index_md)

        # 护栏：必含至少 1 个 source_summary，漏了用模板兜底
        if not any(d.page_type == "source_summary" for d in drafts):
            drafts.append(
                pipeline.PageDraft(
                    title=f"源摘要：{src.filename}",
                    slug=parser.slugify(f"summary-{src.id}"),
                    page_type="source_summary",
                    content_md=f"# {src.filename} 摘要\n\n（自动兜底）实体：{analysis.get('entities')}",
                )
            )

        sid = str(src.id)
        for d in drafts:
            existing = await wiki_repo.get_by_slug(session, src.kb_id, d.slug)
            merged_sources = list(
                dict.fromkeys((existing.source_ids if existing else []) + [sid])
            )
            page = await wiki_repo.upsert(
                session,
                kb_id=src.kb_id,
                slug=d.slug,
                title=d.title,
                page_type=d.page_type,
                content_md=d.content_md,
                frontmatter={**d.frontmatter, "type": d.page_type, "sources": merged_sources},
                source_ids=merged_sources,
            )
            await session.flush()
            await wiki_repo.replace_links(
                session, from_page_id=page.id, to_slugs=pipeline.extract_wikilinks(d.content_md)
            )

        await session.flush()
        # 重建 index 目录页
        pages = await wiki_repo.list_by_kb(session, src.kb_id)
        await wiki_repo.upsert(
            session,
            kb_id=src.kb_id,
            slug="index",
            title="目录",
            page_type="index",
            content_md=_index_markdown(pages),
            frontmatter={"type": "index"},
            source_ids=[],
        )
        await session.flush()
        # 回填 wikilink 目标
        await wiki_repo.backfill_link_targets(session, kb_id=src.kb_id)

        await source_repo.set_status(session, source_id, "done")
    except Exception as exc:  # noqa: BLE001 — 摄入失败要落库可观测
        await source_repo.set_status(session, source_id, "failed", error=str(exc))
