import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingest import parser, pipeline
from app.integrations.storage import StorageBackend
from app.repositories import source_repo, wiki_repo
from app.services import kb_service


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

        # 同批 slug 去重：碰撞者追加序号后缀，避免本批内静默互相覆盖（跨 source 重跑仍走 upsert 幂等）
        seen_slugs: set[str] = set()
        for d in drafts:
            base = d.slug
            n = 2
            while d.slug in seen_slugs:
                d.slug = f"{base}-{n}"
                n += 1
            seen_slugs.add(d.slug)

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
        # 重建 index 目录页（复用 kb_service.rebuild_index，与晋升共用）
        await kb_service.rebuild_index(session, src.kb_id)
        await session.flush()
        # 回填 wikilink 目标
        await wiki_repo.backfill_link_targets(session, kb_id=src.kb_id)

        await source_repo.set_status(session, source_id, "done")
    except Exception as exc:  # noqa: BLE001 — 摄入失败要落库可观测
        # 先回滚清掉失败/半成品事务（否则后续 SELECT 触发 PendingRollbackError、半成品页被提交），
        # 再写 failed 终态；提交统一由调用方(worker tasks.py)负责
        await session.rollback()
        await source_repo.set_status(session, source_id, "failed", error=str(exc))
