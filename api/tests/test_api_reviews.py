from app.core.deps import get_current_user
from app.main import app
from app.repositories import kb_repo, wiki_repo
from app.services import org_service


async def _setup(session):
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    alice = await org_service.create_user(
        session, email="alice@x.com", password="pw123456", display_name="Alice", role="user"
    )
    company = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    alice_kb = (await kb_repo.list_by_scope(session, "personal", alice.id))[0]
    page = await wiki_repo.upsert(
        session, kb_id=alice_kb.id, slug="想法", title="好想法",
        page_type="concept", content_md="内容", frontmatter={}, source_ids=[],
    )
    await session.commit()
    return admin, alice, company, page


async def test_promote_review_approve_flow(session, client):
    admin, alice, company, page = await _setup(session)
    app.dependency_overrides[get_current_user] = lambda: alice
    try:
        r = await client.post(
            f"/api/pages/{page.id}/promote", json={"to_kb_id": str(company.id), "note": "上公司"}
        )
        assert r.status_code == 200
        pr_id = r.json()["id"]
        assert (await client.get("/api/reviews")).json() == []  # alice 看不到公司审核队列
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        rev = await client.get("/api/reviews")
        assert any(x["id"] == pr_id for x in rev.json())  # admin 队列见到
        ap = await client.post(f"/api/reviews/{pr_id}/approve")
        assert ap.status_code == 200 and ap.json()["status"] == "approved"
        pages = await client.get(f"/api/kbs/{company.id}/pages")
        assert any(p["slug"] == "想法" for p in pages.json())  # 已晋升到公司 KB
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_non_reviewer_cannot_approve(session, client):
    admin, alice, company, page = await _setup(session)
    app.dependency_overrides[get_current_user] = lambda: alice
    try:
        r = await client.post(f"/api/pages/{page.id}/promote", json={"to_kb_id": str(company.id)})
        pr_id = r.json()["id"]
        ap = await client.post(f"/api/reviews/{pr_id}/approve")  # alice 批不了公司
        assert ap.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
