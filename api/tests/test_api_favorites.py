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


async def test_favorite_toggle_and_list(session, client):
    admin, page = await _admin_company_page(session)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        assert (await client.post(f"/api/pages/{page.id}/favorite")).status_code == 204
        # 详情显示已收藏
        assert (await client.get(f"/api/pages/{page.id}")).json()["data"]["is_favorited"] is True
        # 我的收藏含该页
        favs = await client.get("/api/favorites")
        assert any(p["id"] == str(page.id) for p in favs.json()["data"])
        # 重复收藏幂等
        assert (await client.post(f"/api/pages/{page.id}/favorite")).status_code == 204
        assert len((await client.get("/api/favorites")).json()["data"]) == 1
        # 取消收藏
        assert (await client.delete(f"/api/pages/{page.id}/favorite")).status_code == 204
        assert (await client.get("/api/favorites")).json()["data"] == []
        assert (await client.get(f"/api/pages/{page.id}")).json()["data"]["is_favorited"] is False
    finally:
        app.dependency_overrides.pop(get_current_user, None)
