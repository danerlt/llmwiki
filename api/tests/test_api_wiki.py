from app.core.deps import get_current_user
from app.main import app
from app.repositories import kb_repo, org_repo, source_repo, wiki_repo
from app.services import org_service


async def test_list_pages_forbidden_for_inaccessible_kb(session, client):
    frontend = await org_repo.create_department(session, name="前端组", parent_id=None)
    await session.flush()
    frontend_kb = await kb_repo.create(session, scope_type="department", scope_ref_id=frontend.id, name="前端组")
    backend = await org_repo.create_department(session, name="后端组", parent_id=None)
    await session.flush()
    alice = await org_service.create_user(
        session, email="alice@x.com", password="pw123456", display_name="Alice", department_id=backend.id
    )
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: alice
    try:
        r = await client.get(f"/api/kbs/{frontend_kb.id}/pages")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_get_page_detail_accessible(session, client):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    page = await wiki_repo.upsert(session, kb_id=kb.id, slug="p", title="P",
                                  page_type="entity", content_md="内容", frontmatter={}, source_ids=["s1"])
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        r = await client.get(f"/api/pages/{page.id}")
        assert r.status_code == 200
        assert r.json()["content_md"] == "内容"
        assert r.json()["source_ids"] == ["s1"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def _admin_company_kb(session):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    await session.commit()
    return admin, kb


async def test_create_edit_history_revert_flow(session, client):
    admin, kb = await _admin_company_kb(session)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        # 创建
        r = await client.post(
            f"/api/kbs/{kb.id}/pages",
            json={"title": "手写页", "content_md": "第一版 [[相关]]", "page_type": "concept"},
        )
        assert r.status_code == 201
        pid = r.json()["id"]
        assert r.json()["content_md"] == "第一版 [[相关]]"

        # 编辑
        r2 = await client.put(f"/api/pages/{pid}", json={"content_md": "第二版"})
        assert r2.status_code == 200 and r2.json()["content_md"] == "第二版"

        # 历史：两个版本（v2 在前）
        rv = await client.get(f"/api/pages/{pid}/versions")
        assert rv.status_code == 200
        vers = rv.json()
        assert [v["version_no"] for v in vers] == [2, 1]
        assert vers[1]["content_md"] == "第一版 [[相关]]"

        # 回滚到 v1 → 内容回到第一版，且新增 v3
        rr = await client.post(f"/api/pages/{pid}/revert/1")
        assert rr.status_code == 200 and rr.json()["content_md"] == "第一版 [[相关]]"
        rv2 = await client.get(f"/api/pages/{pid}/versions")
        assert [v["version_no"] for v in rv2.json()] == [3, 2, 1]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_page_tags_create_and_filter(session, client):
    admin, kb = await _admin_company_kb(session)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        r = await client.post(
            f"/api/kbs/{kb.id}/pages",
            json={"title": "带标签", "content_md": "x", "tags": ["后端", "python"]},
        )
        assert r.status_code == 201 and set(r.json()["tags"]) == {"后端", "python"}
        await client.post(f"/api/kbs/{kb.id}/pages", json={"title": "无标签", "slug": "no-tag"})
        filtered = await client.get(f"/api/kbs/{kb.id}/pages?tag=python")
        titles = [p["title"] for p in filtered.json()]
        assert "带标签" in titles and "无标签" not in titles
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_create_page_forbidden_without_write(session, client):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    user = await org_service.create_user(
        session, email="u@x.com", password="pw123456", display_name="U", role="user"
    )
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        r = await client.post(f"/api/kbs/{kb.id}/pages", json={"title": "X", "content_md": ""})
        assert r.status_code == 403  # 普通用户无公司库写权限
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_create_page_duplicate_slug_conflict(session, client):
    admin, kb = await _admin_company_kb(session)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        await client.post(f"/api/kbs/{kb.id}/pages", json={"title": "X", "slug": "dup"})
        r = await client.post(f"/api/kbs/{kb.id}/pages", json={"title": "Y", "slug": "dup"})
        assert r.status_code == 409
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_create_rejects_system_page_type(session, client):
    admin, kb = await _admin_company_kb(session)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        r = await client.post(
            f"/api/kbs/{kb.id}/pages", json={"title": "X", "page_type": "index"}
        )
        assert r.status_code == 422  # 不可手工指定系统页类型
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_delete_page(session, client):
    admin, kb = await _admin_company_kb(session)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        pid = (
            await client.post(f"/api/kbs/{kb.id}/pages", json={"title": "待删", "slug": "del"})
        ).json()["id"]
        assert (await client.delete(f"/api/pages/{pid}")).status_code == 204
        assert (await client.get(f"/api/pages/{pid}")).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_get_page_hides_cross_kb_source_filenames(session, client):
    company = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    bob = await org_service.create_user(
        session, email="bob@x.com", password="pw123456", display_name="Bob", role="user"
    )
    await session.flush()
    bob_kb = (await kb_repo.list_by_scope(session, "personal", bob.id))[0]  # admin 不可见
    secret = await source_repo.create(
        session, kb_id=bob_kb.id, uploader_id=bob.id, filename="bob机密.pdf",
        content_type="application/pdf", storage_key="k",
    )
    await session.flush()
    # 公司页（admin 可读）引用了 bob 私库的 source（模拟晋升复制后的残留）
    page = await wiki_repo.upsert(
        session, kb_id=company.id, slug="p", title="P", page_type="entity",
        content_md="x", frontmatter={}, source_ids=[str(secret.id)],
    )
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        r = await client.get(f"/api/pages/{page.id}")
        assert r.status_code == 200
        assert r.json()["sources"] == []  # 跨库来源文件名不泄漏
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_get_page_includes_outlinks(session, client):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    a = await wiki_repo.upsert(session, kb_id=kb.id, slug="a", title="A",
                               page_type="entity", content_md="见 [[b]]", frontmatter={}, source_ids=[])
    b = await wiki_repo.upsert(session, kb_id=kb.id, slug="b", title="B",
                              page_type="concept", content_md="x", frontmatter={}, source_ids=[])
    await session.flush()
    await wiki_repo.replace_links(session, from_page_id=a.id, to_slugs=["b"])
    await session.flush()
    await wiki_repo.backfill_link_targets(session, kb_id=kb.id)
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        r = await client.get(f"/api/pages/{a.id}")
        assert r.status_code == 200
        outs = r.json()["outlinks"]
        assert [o["slug"] for o in outs] == ["b"]  # 本页出链含已解析的 b
    finally:
        app.dependency_overrides.pop(get_current_user, None)
