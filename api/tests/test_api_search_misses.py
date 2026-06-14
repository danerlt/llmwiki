from app.core.deps import get_current_user
from app.main import app
from app.repositories import kb_repo, search_miss_repo, wiki_repo
from app.services import org_service


async def _company_kb_with_page(session):
    """建一个 company 域 KB（对所有用户可见）+ 一个含 'Python' 的页。"""
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    await wiki_repo.upsert(
        session, kb_id=kb.id, slug="python", title="Python 指南", page_type="concept",
        content_md="Python 是一门编程语言", frontmatter={}, source_ids=[],
    )
    await session.flush()
    return kb


async def _user(session, email="u@x.com", role="user"):
    return await org_service.create_user(
        session, email=email, password="pw123456", display_name="U", role=role
    )


async def test_zero_result_search_records_miss(session, client):
    await _company_kb_with_page(session)
    user = await _user(session)
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        r = await client.get("/api/search", params={"q": "区块链"})
        assert r.status_code == 200 and r.json()["data"] == []  # 无果
        queries = {q for q, _c, _ls in await search_miss_repo.top(session)}
        assert "区块链" in queries  # 无果词被记录为知识空缺
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_hit_search_records_no_miss(session, client):
    await _company_kb_with_page(session)
    user = await _user(session)
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        r = await client.get("/api/search", params={"q": "Python"})
        assert r.status_code == 200 and len(r.json()["data"]) >= 1  # 命中
        assert await search_miss_repo.top(session) == []  # 命中不记无果
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_page_type_filtered_empty_not_recorded(session, client):
    await _company_kb_with_page(session)
    user = await _user(session)
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        # 带 page_type 过滤导致的空结果不是知识空缺，不记录
        r = await client.get("/api/search", params={"q": "Python", "page_type": "overview"})
        assert r.status_code == 200 and r.json()["data"] == []
        assert await search_miss_repo.top(session) == []
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_misses_aggregated_and_exposed_in_analytics(session, client):
    await _company_kb_with_page(session)
    user = await _user(session)
    admin = await _user(session, email="admin@x.com", role="admin")
    await session.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        await client.get("/api/search", params={"q": "区块链"})
        await client.get("/api/search", params={"q": "区块链"})  # 同词两次 → 聚合 count=2
        await client.get("/api/search", params={"q": "量子计算"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        r = await client.get("/api/analytics")
        assert r.status_code == 200
        misses = {m["query"]: m["count"] for m in r.json()["data"]["search_misses"]}
        assert misses.get("区块链") == 2  # 按词聚合计数
        assert misses.get("量子计算") == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)
