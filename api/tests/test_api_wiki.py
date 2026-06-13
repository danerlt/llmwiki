from app.core.deps import get_current_user
from app.main import app
from app.repositories import kb_repo, org_repo, wiki_repo
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
