from app.core.deps import get_current_user
from app.main import app
from app.repositories import kb_repo, wiki_repo
from app.services import org_service


async def _admin_company_page(session):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    page = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="p", title="P", page_type="concept",
        content_md="x", frontmatter={}, source_ids=[],
    )
    await session.commit()
    return admin, page


async def test_add_list_delete_comment(session, client):
    admin, page = await _admin_company_page(session)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        r = await client.post(f"/api/pages/{page.id}/comments", json={"body": "第一条评论"})
        assert r.status_code == 201
        cid = r.json()["id"]
        assert r.json()["author_name"] == "Admin"

        lst = await client.get(f"/api/pages/{page.id}/comments")
        assert lst.status_code == 200 and len(lst.json()) == 1

        d = await client.delete(f"/api/comments/{cid}")
        assert d.status_code == 204
        assert (await client.get(f"/api/pages/{page.id}/comments")).json() == []
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_cannot_comment_on_inaccessible_page(session, client):
    # 在不可见 KB 的页上评论应 403
    other = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    from app.repositories import org_repo

    dept = await org_repo.create_department(session, name="独立部", parent_id=None)
    await session.flush()
    dept_kb = await kb_repo.create(session, scope_type="department", scope_ref_id=dept.id, name="独立部")
    await session.flush()
    page = await wiki_repo.upsert(
        session, kb_id=dept_kb.id, slug="s", title="S", page_type="concept",
        content_md="x", frontmatter={}, source_ids=[],
    )
    outsider = await org_service.create_user(
        session, email="out@x.com", password="pw123456", display_name="Out", role="user"
    )
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: outsider
    try:
        r = await client.post(f"/api/pages/{page.id}/comments", json={"body": "x"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_non_author_cannot_delete_comment(session, client):
    admin, page = await _admin_company_page(session)
    other = await org_service.create_user(
        session, email="other@x.com", password="pw123456", display_name="Other", role="user"
    )
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        cid = (await client.post(f"/api/pages/{page.id}/comments", json={"body": "hi"})).json()["id"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_current_user] = lambda: other
    try:
        # 普通用户(非作者、非 admin)不能删他人评论
        assert (await client.delete(f"/api/comments/{cid}")).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
