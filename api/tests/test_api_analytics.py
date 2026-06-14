from app.core.deps import get_current_user
from app.main import app
from app.repositories import feedback_repo, kb_repo, wiki_repo
from app.services import org_service


async def test_analytics_orphan_stale_and_feedback(session, client):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    # 一个孤儿页（无任何链接）
    orphan = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="orphan", title="孤儿页", page_type="concept",
        content_md="无链接", frontmatter={}, source_ids=[],
    )
    # 两个互链页（非孤儿）
    a = await wiki_repo.upsert(session, kb_id=kb.id, slug="a", title="A", page_type="concept",
                              content_md="见 [[b]]", frontmatter={}, source_ids=[])
    await wiki_repo.upsert(session, kb_id=kb.id, slug="b", title="B", page_type="concept",
                          content_md="x", frontmatter={}, source_ids=[])
    await session.flush()
    await wiki_repo.replace_links(session, from_page_id=a.id, to_slugs=["b"])
    await session.flush()
    await wiki_repo.backfill_link_targets(session, kb_id=kb.id)
    await feedback_repo.create(session, user_id=admin.id, question="q", answer="ans", vote="up")
    await session.commit()

    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        r = await client.get("/api/analytics?stale_days=3650")
        assert r.status_code == 200
        body = r.json()
        assert body["feedback"]["up"] == 1
        orphan_titles = [p["title"] for p in body["orphan_pages"]]
        assert "孤儿页" in orphan_titles and "A" not in orphan_titles  # 互链页不是孤儿
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_analytics_review_due_lists_stale_verified(session, client):
    from datetime import datetime, timezone

    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    page = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="old-verified", title="陈年认证页", page_type="concept",
        content_md="x", frontmatter={}, source_ids=[],
    )
    await session.flush()
    page.verified_by = admin.id
    page.verified_at = datetime(2020, 1, 1, tzinfo=timezone.utc)  # 很久以前认证
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        r = await client.get("/api/analytics?stale_days=30")
        ids = [p["id"] for p in r.json()["review_due_pages"]]
        assert str(page.id) in ids  # 认证超期 → 待复审
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_analytics_admin_only(session, client):
    user = await org_service.create_user(
        session, email="u@x.com", password="pw123456", display_name="U", role="user"
    )
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        assert (await client.get("/api/analytics")).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
