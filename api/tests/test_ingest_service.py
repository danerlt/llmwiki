import json

import pytest_asyncio

from app.models import KnowledgeBase, User
from app.repositories import source_repo, wiki_repo
from app.services import ingest_service
from tests.fakes import FakeStorage


def _llm(analysis: dict, pages: list[dict]) -> "FakeLLM":
    from tests.fakes import FakeLLM

    return FakeLLM([json.dumps(analysis), json.dumps(pages)])


@pytest_asyncio.fixture
async def kb_and_source(session):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name="公司")
    u = User(email="a@x.com", password_hash="h", display_name="A", role="admin")
    session.add_all([kb, u])
    await session.flush()
    storage = FakeStorage()
    storage.put("k1", "技术部负责后端。".encode(), "text/markdown")
    src = await source_repo.create(
        session, kb_id=kb.id, uploader_id=u.id, filename="a.md",
        content_type="text/markdown", storage_key="k1",
    )
    await session.commit()  # 模拟真实流程：source 由上传端点先提交，ingest 失败 rollback 不应误伤
    return kb, src, storage


async def test_pages_have_sources_and_links(session, kb_and_source):
    kb, src, storage = kb_and_source
    llm = _llm(
        {"entities": ["技术部"], "concepts": ["后端"]},
        [
            {"title": "技术部", "slug": "技术部", "page_type": "entity",
             "content_md": "技术部，见 [[后端]]"},
            {"title": "后端", "slug": "后端", "page_type": "concept", "content_md": "后端开发"},
            {"title": "源摘要", "slug": "源摘要", "page_type": "source_summary", "content_md": "摘要"},
        ],
    )
    await ingest_service.ingest_source(session, src.id, llm=llm, storage=storage)
    await session.flush()

    pages = {p.slug: p for p in await wiki_repo.list_by_kb(session, kb.id)}
    assert "技术部" in pages and "后端" in pages
    # 每个内容页都带本 source 的溯源
    assert str(src.id) in pages["技术部"].source_ids
    # wikilink 已写入并回填
    links = await wiki_repo.links_from(session, pages["技术部"].id)
    assert any(l.to_slug == "后端" and l.to_page_id == pages["后端"].id for l in links)
    # index 目录页自动生成
    assert "index" in {p.page_type for p in pages.values()}
    # 状态完成
    refreshed = await source_repo.get_by_id(session, src.id)
    assert refreshed.status == "done"


async def test_fallback_summary_when_llm_omits(session, kb_and_source):
    kb, src, storage = kb_and_source
    # LLM 只产出 entity，没有 source_summary
    llm = _llm(
        {"entities": ["X"]},
        [{"title": "X", "slug": "x", "page_type": "entity", "content_md": "x"}],
    )
    await ingest_service.ingest_source(session, src.id, llm=llm, storage=storage)
    await session.flush()
    pages = await wiki_repo.list_by_kb(session, kb.id)
    assert any(p.page_type == "source_summary" for p in pages)  # 兜底补齐


async def test_idempotent_rerun(session, kb_and_source):
    kb, src, storage = kb_and_source
    pages_json = [{"title": "X", "slug": "x", "page_type": "entity", "content_md": "x"}]
    await ingest_service.ingest_source(
        session, src.id, llm=_llm({"entities": ["X"]}, pages_json), storage=storage
    )
    await session.flush()
    n1 = len(await wiki_repo.list_by_kb(session, kb.id))
    await ingest_service.ingest_source(
        session, src.id, llm=_llm({"entities": ["X"]}, pages_json), storage=storage
    )
    await session.flush()
    n2 = len(await wiki_repo.list_by_kb(session, kb.id))
    assert n1 == n2  # 重跑不产生重复页


async def test_failure_sets_status_failed(session, kb_and_source):
    kb, src, storage = kb_and_source

    class BoomLLM:
        async def complete(self, system, user):
            raise RuntimeError("llm down")

    await ingest_service.ingest_source(session, src.id, llm=BoomLLM(), storage=storage)
    await session.flush()
    refreshed = await source_repo.get_by_id(session, src.id)
    assert refreshed.status == "failed" and "llm down" in (refreshed.error or "")


async def test_failure_after_flush_still_sets_failed(session, kb_and_source, monkeypatch):
    """页已 flush 之后才失败时，except 先 rollback（清掉污染事务，否则后续写会因 PendingRollbackError 崩），
    仍能把 failed 落库。M8“不残留半成品页”由 rollback-first 构造保证（rollback 丢弃所有未提交页）。"""
    kb, src, storage = kb_and_source

    async def _boom(session, *, kb_id):
        raise RuntimeError("backfill boom")

    monkeypatch.setattr(wiki_repo, "backfill_link_targets", _boom)
    llm = _llm(
        {"entities": ["X"]},
        [{"title": "X", "slug": "x", "page_type": "entity", "content_md": "x"}],
    )

    await ingest_service.ingest_source(session, src.id, llm=llm, storage=storage)  # 不应抛异常

    refreshed = await source_repo.get_by_id(session, src.id)
    assert refreshed.status == "failed"


async def test_same_batch_slug_collision_kept_separate(session, kb_and_source):
    """同批 C++ / C# 经 slugify 都得 'c'，应去重为两页而非互相覆盖。"""
    kb, src, storage = kb_and_source
    llm = _llm(
        {"entities": ["C++", "C#"]},
        [
            {"title": "C++", "slug": "C++", "page_type": "entity", "content_md": "cpp"},
            {"title": "C#", "slug": "C#", "page_type": "entity", "content_md": "csharp"},
        ],
    )
    await ingest_service.ingest_source(session, src.id, llm=llm, storage=storage)
    await session.flush()
    contents = {
        p.content_md for p in await wiki_repo.list_by_kb(session, kb.id) if p.page_type == "entity"
    }
    assert "cpp" in contents and "csharp" in contents
