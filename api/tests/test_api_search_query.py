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
        kb_ids = {p["kb_id"] for p in r.json()["data"]}
        assert str(frontend_kb.id) not in kb_ids   # 平级前端组不可见——铁律
        assert str(backend_kb.id) in kb_ids
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_query_rejects_overlong_question(session, client):
    alice, _, _ = await _two_dept_kbs_with_pages(session)
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: alice
    try:
        r = await client.post("/api/query", json={"question": "问" * 2001})
        assert r.status_code == 422  # 超长问题在边界拒绝，不放大下游 LLM 成本
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_search_filters_by_page_type(session, client):
    alice, backend_kb, _ = await _two_dept_kbs_with_pages(session)
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: alice
    try:
        # backend_kb 的页是 entity 类型
        ent = await client.get("/api/search", params={"q": "后端", "page_type": "entity"})
        assert ent.status_code == 200 and len(ent.json()["data"]) >= 1
        # 过滤为 overview → 无结果
        ov = await client.get("/api/search", params={"q": "后端", "page_type": "overview"})
        assert ov.json()["data"] == []
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_query_feedback_recorded(session, client):
    alice, _, _ = await _two_dept_kbs_with_pages(session)
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: alice
    try:
        r = await client.post(
            "/api/query/feedback",
            json={"question": "后端", "answer": "后端用 Python。", "vote": "up"},
        )
        assert r.status_code == 201
        from app.repositories import feedback_repo

        assert (await feedback_repo.counts(session)).get("up") == 1
        # 非法 vote 被拒
        bad = await client.post(
            "/api/query/feedback", json={"question": "x", "answer": "y", "vote": "meh"}
        )
        assert bad.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_query_stream_emits_deltas_and_citations(session, client):
    alice, backend_kb, frontend_kb = await _two_dept_kbs_with_pages(session)
    await session.commit()
    fake_llm = FakeLLM(["后端机密讲了后端内容[1]。"])
    app.dependency_overrides[get_current_user] = lambda: alice
    app.dependency_overrides[query_ctrl.get_llm] = lambda: fake_llm
    try:
        r = await client.post("/api/query/stream", json={"question": "后端"})
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        body = r.text
        assert "data:" in body
        # 把所有 delta 拼起来应还原答案
        import json as _json

        deltas, citations = [], None
        for line in body.splitlines():
            if not line.startswith("data:"):
                continue
            evt = _json.loads(line[5:].strip())
            if "delta" in evt:
                deltas.append(evt["delta"])
            if evt.get("done"):
                citations = evt.get("citations")
        assert "".join(deltas).startswith("后端机密")
        assert citations is not None
        cited_kbs = {c["kb_id"] for c in citations}
        assert str(frontend_kb.id) not in cited_kbs  # 引用只来自可见 KB
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(query_ctrl.get_llm, None)


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
        body = r.json()["data"]
        assert "[1]" in body["answer"]
        cited_kbs = {c["kb_id"] for c in body["citations"]}
        assert str(frontend_kb.id) not in cited_kbs   # 引用只来自可见 KB
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(query_ctrl.get_llm, None)
