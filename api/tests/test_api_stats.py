from app.core.deps import get_current_user
from app.main import app
from app.repositories import kb_repo, wiki_repo
from app.services import org_service


async def test_stats_and_kb_page_count(session, client):
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    await wiki_repo.upsert(session, kb_id=kb.id, slug="p1", title="P1",
                           page_type="entity", content_md="x", frontmatter={}, source_ids=[])
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        r = await client.get("/api/stats")
        assert r.status_code == 200
        body = r.json()
        assert body["page_count"] >= 1 and body["kb_count"] >= 1
        kbs = await client.get("/api/kbs")
        assert any(k["page_count"] >= 1 for k in kbs.json())  # /kbs 现在带页数
    finally:
        app.dependency_overrides.pop(get_current_user, None)
