from app.repositories import kb_repo, wiki_repo
from app.services import org_service, query_service
from tests.fakes import FakeLLM


async def test_answer_assembles_context_and_returns_citations(session):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    await session.flush()
    await wiki_repo.upsert(session, kb_id=kb.id, slug="后端", title="后端",
                           page_type="entity", content_md="服务端开发", frontmatter={}, source_ids=[])
    await session.flush()

    llm = FakeLLM(["后端指服务端开发[1]。"])
    # MVP 关键词召回为整串子串匹配，传关键词“后端”（spec：中文用 trgm 子串兜底）
    out = await query_service.answer(session, admin, "后端", llm=llm)
    assert out["answer"] == "后端指服务端开发[1]。"
    assert any(c["title"] == "后端" for c in out["citations"])
    # LLM 收到的 user prompt 含编号资料
    assert "[1]" in llm.calls[0][1]


async def test_answer_empty_when_no_pages(session):
    admin = await org_service.create_user(
        session, email="a@x.com", password="pw123456", display_name="A", role="admin"
    )
    await session.flush()
    llm = FakeLLM(["不应被调用"])
    out = await query_service.answer(session, admin, "无关问题", llm=llm)
    assert out["citations"] == []
    assert llm.calls == []   # 无资料则不调用 LLM
