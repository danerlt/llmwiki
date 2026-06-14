from app.services import embedding_service


def test_cosine_of_normalized_vectors():
    assert embedding_service.cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert embedding_service.cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert embedding_service.cosine([], [1.0]) == 0.0  # 维度不匹配/空 → 0


def test_embed_disabled_returns_none(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "embeddings_enabled", False)
    assert embedding_service.embed("任意文本") is None  # 关闭时不依赖 torch


async def test_ingest_stores_embedding_when_enabled(session, monkeypatch):
    """启用时（用假 embedder）摄入应给页写入向量。"""
    import json

    from app.models import KnowledgeBase, User
    from app.repositories import source_repo, wiki_repo
    from app.services import embedding_service as es, ingest_service
    from tests.fakes import FakeLLM, FakeStorage

    monkeypatch.setattr(es, "enabled", lambda: True)
    monkeypatch.setattr(es, "embed", lambda text: [0.1, 0.2, 0.3])

    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name="公司")
    u = User(email="e@x.com", password_hash="h", display_name="E", role="admin")
    session.add_all([kb, u])
    await session.flush()
    storage = FakeStorage()
    storage.put("k", b"text", "text/markdown")
    src = await source_repo.create(
        session, kb_id=kb.id, uploader_id=u.id, filename="a.md",
        content_type="text/markdown", storage_key="k",
    )
    await session.commit()
    llm = FakeLLM([
        json.dumps({"entities": ["X"]}),
        json.dumps([{"title": "X", "slug": "x", "page_type": "entity", "content_md": "y"}]),
    ])
    await ingest_service.ingest_source(session, src.id, llm=llm, storage=storage)
    await session.flush()
    pages = {p.slug: p for p in await wiki_repo.list_by_kb(session, kb.id)}
    assert pages["x"].embedding == [0.1, 0.2, 0.3]
