from app.core.deps import get_current_user
from app.main import app
from app.repositories import kb_repo, wiki_repo
from app.services import org_service


async def _setup(session):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    bob = await org_service.create_user(
        session, email="bob@x.com", password="pw123456", display_name="Bob", role="user"
    )
    page = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="p", title="共享页", page_type="concept",
        content_md="x", frontmatter={}, source_ids=[],
    )
    await session.commit()
    return admin, bob, page


async def test_subscribe_then_edit_notifies_watcher(session, client):
    admin, bob, page = await _setup(session)
    # bob 关注该页
    app.dependency_overrides[get_current_user] = lambda: bob
    try:
        assert (await client.post(f"/api/pages/{page.id}/subscribe")).status_code == 204
        assert (await client.get(f"/api/pages/{page.id}")).json()["is_subscribed"] is True
        assert (await client.get("/api/notifications/unread-count")).json()["count"] == 0
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # admin 编辑该页
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        await client.put(f"/api/pages/{page.id}", json={"content_md": "改了"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # bob 收到通知
    app.dependency_overrides[get_current_user] = lambda: bob
    try:
        assert (await client.get("/api/notifications/unread-count")).json()["count"] == 1
        notes = (await client.get("/api/notifications")).json()
        assert len(notes) == 1 and notes[0]["type"] == "page.updated"
        # 标记全部已读
        assert (await client.post("/api/notifications/read")).status_code == 204
        assert (await client.get("/api/notifications/unread-count")).json()["count"] == 0
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_actor_not_notified_of_own_edit(session, client):
    admin, bob, page = await _setup(session)
    # admin 自己关注并自己编辑 → 不应给自己发通知
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        await client.post(f"/api/pages/{page.id}/subscribe")
        await client.put(f"/api/pages/{page.id}", json={"content_md": "自己改"})
        assert (await client.get("/api/notifications/unread-count")).json()["count"] == 0
    finally:
        app.dependency_overrides.pop(get_current_user, None)
