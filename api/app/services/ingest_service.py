import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingest import parser, pipeline
from app.integrations.storage import StorageBackend
from app.repositories import source_repo, wiki_repo
from app.services import kb_service

_logger = logging.getLogger("app.ingest")


def _failure_code(exc: Exception) -> str:
    """脱敏错误码：只暴露稳定类别/类名，绝不把可能含 SQL/存储路径/密钥的 str(exc)
    返回给用户（该字段经 SourceOut 透传给任何对该 KB 有读权限者）。完整异常进服务端日志。"""
    mod = (type(exc).__module__ or "").split(".")[0]
    if mod == "httpx":
        return "llm_unavailable"
    if mod == "minio":
        return "storage_unavailable"
    return type(exc).__name__


def _is_transient(exc: Exception) -> bool:
    """瞬时/可重试故障：上游 LLM(httpx) 或对象存储(minio) 抖动，重试可能成功；
    解析错误/数据错误等视为永久失败，不重试。"""
    return (type(exc).__module__ or "").split(".")[0] in {"httpx", "minio"}


async def _prune_orphans(
    session: AsyncSession, kb_id: uuid.UUID, sid: str, keep_slugs: set[str]
) -> None:
    """清理本 source 上一轮产出、本次未再生成的孤儿页（保证 reingest 幂等）。

    页可由多个 source 派生：仅摘除本 sid；若摘除后再无其它来源支撑，则删除该孤儿页。
    """
    for p in await wiki_repo.list_by_kb(session, kb_id):
        if sid not in (p.source_ids or []) or p.slug in keep_slugs:
            continue
        remaining = [s for s in p.source_ids if s != sid]
        if remaining:
            p.source_ids = remaining  # 仍有其它来源，保留页、仅去除本溯源
        else:
            await wiki_repo.delete_page(session, p.id)


async def ingest_source(
    session: AsyncSession,
    source_id: uuid.UUID,
    *,
    llm,
    storage: StorageBackend,
) -> None:
    """确定性两步摄入：认领→解析→分析→生成→落页→链接图→重建 index。

    并发去重靠 source_repo.claim（同一 source 仅一个 job 处理，避免双写触发唯一约束冲突）；
    processing 提前提交以对外可见并充当行级互斥；瞬时故障(LLM/存储抖动)重新抛出由 arq 重试，
    永久故障写 failed 终态（脱敏错误码，完整异常仅进服务端日志）。
    """
    src = await source_repo.get_by_id(session, source_id)
    if src is None:
        return
    if not await source_repo.claim(session, source_id):
        return  # 另一个 job 已认领该源，跳过
    await session.commit()  # processing 落库：对外可见 + 行级互斥已生效
    try:
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

        # 清理本 source 上一轮产出、本次未再生成的孤儿页（reingest 幂等；seen_slugs 即本次全部 slug）
        await _prune_orphans(session, src.kb_id, sid, seen_slugs)
        await session.flush()
        # 重建 index 目录页（复用 kb_service.rebuild_index，与晋升共用）
        await kb_service.rebuild_index(session, src.kb_id)
        await session.flush()
        # 回填 wikilink 目标
        await wiki_repo.backfill_link_targets(session, kb_id=src.kb_id)

        await source_repo.set_status(session, source_id, "done")
        await session.commit()
    except Exception as exc:  # noqa: BLE001 — 摄入失败要落库可观测
        # 先回滚清掉半成品事务（否则后续 SELECT 触发 PendingRollbackError、半成品页被提交），
        # 再写 failed 终态并提交。
        await session.rollback()
        _logger.exception("摄入失败 source_id=%s", source_id)  # 完整异常仅进服务端日志
        await source_repo.set_status(session, source_id, "failed", error=_failure_code(exc))
        await session.commit()
        if _is_transient(exc):
            raise  # 瞬时故障：抛出让 arq 走 max_tries 重试（下次 claim 会重新认领 failed 源）
