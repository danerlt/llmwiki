from app.controllers import query as query_ctrl
from app.core.deps import get_current_user
from app.main import app
from app.repositories import kb_repo, org_repo, wiki_repo
from app.services import org_service
from tests.fakes import FakeLLM


async def _two_dept_kbs_with_pages(session):
    tech = await org_repo.create_department(session, name="技术部", parent_id=None)
    await session.flush()
    backend = await org_repo.create_department(session, name="后端组", parent_id=tech.id)
    frontend = await org_repo.create_department(session, name="前端组", parent_id=tech.id)
    await session.flush()
    backend_kb = await kb_repo.create(session, scope_type="department", scope_ref_id=backend.id, name="后端组")
    frontend_kb = await kb_repo.create(session, scope_type="department", scope_ref_id=frontend.id, name="前端组")
    await session.flush()
    alice = await org_service.create_user(
        session, email="alice@x.com", password="pw123456", display_name="Alice", department_id=backend.id
    )
    await session.flush()
    await wiki_repo.upsert(session, kb_id=backend_kb.id, slug="b", title="后端机密",
                           page_type="entity", content_md="后端内容", frontmatter={}, source_ids=[])
    await wiki_repo.upsert(session, kb_id=frontend_kb.id, slug="f", title="后端禁地",
                           page_type="entity", content_md="后端内容", frontmatter={}, source_ids=[])
    await session.flush()
    return alice, backend_kb, frontend_kb


async def test_search_filters_inaccessible(session, client):
    alice, backend_kb, frontend_kb = await _two_dept_kbs_with_pages(session)
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: alice
    try:
        r = await client.get("/api/search", params={"q": "后端"})
        assert r.status_code == 200
        kb_ids = {p["kb_id"] for p in r.json()}
        assert str(frontend_kb.id) not in kb_ids   # 平级前端组不可见——铁律
        assert str(backend_kb.id) in kb_ids
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_query_returns_answer_and_citations(session, client):
    alice, backend_kb, frontend_kb = await _two_dept_kbs_with_pages(session)
    await session.commit()
    fake_llm = FakeLLM(["后端机密讲了后端内容[1]。"])
    app.dependency_overrides[get_current_user] = lambda: alice
    app.dependency_overrides[query_ctrl.get_llm] = lambda: fake_llm
    try:
        # MVP 关键词召回为子串匹配，传关键词“后端”
        r = await client.post("/api/query", json={"question": "后端"})
        assert r.status_code == 200
        body = r.json()
        assert "[1]" in body["answer"]
        cited_kbs = {c["kb_id"] for c in body["citations"]}
        assert str(frontend_kb.id) not in cited_kbs   # 引用只来自可见 KB
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(query_ctrl.get_llm, None)
