from app.core.deps import get_current_user
from app.main import app
from app.repositories import kb_repo, wiki_repo
from app.services import org_service


async def test_activity_merges_updates_and_comments(session, client):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    page = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="p", title="动态页", page_type="concept",
        content_md="x", frontmatter={}, source_ids=[],
    )
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        await client.post(f"/api/pages/{page.id}/comments", json={"body": "评论一下"})
        r = await client.get("/api/activity")
        assert r.status_code == 200
        items = r.json()["data"]
        types = [i["type"] for i in items]
        assert "page.commented" in types  # 评论进入活动流
        assert any(i["page_id"] == str(page.id) for i in items)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
