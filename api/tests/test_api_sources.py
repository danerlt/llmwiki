import uuid

from app.controllers import sources as sources_ctrl
from app.core.deps import get_current_user
from app.main import app
from app.repositories import kb_repo, source_repo
from app.services import org_service
from tests.fakes import FakeStorage


async def _setup_user_kb(session, role="admin"):
    user = await org_service.create_user(
        session, email=f"{role}@x.com", password="pw123456", display_name=role, role=role
    )
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    return user, kb


async def test_upload_creates_pending_source(session, client):
    user, kb = await _setup_user_kb(session)
    await session.commit()

    fake_storage = FakeStorage()
    enqueued: list[str] = []

    app.dependency_overrides[sources_ctrl.get_storage] = lambda: fake_storage
    app.dependency_overrides[get_current_user] = lambda: user

    async def _fake_enqueue(source_id: str) -> str:
        enqueued.append(source_id)
        return "job-xyz"

    sources_ctrl.enqueue_ingest = _fake_enqueue  # monkeypatch 入队
    try:
        r = await client.post(
            f"/api/kbs/{kb.id}/sources",
            files={"file": ("a.md", b"# hi", "text/markdown")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "pending"
        sid = body["source_id"]
        assert enqueued == [sid]
        # 落库且 job_id 回写
        refreshed = await source_repo.get_by_id(session, uuid.UUID(sid))
        assert refreshed.status == "pending" and refreshed.job_id == "job-xyz"
        assert fake_storage.objects  # 文件已存储
    finally:
        app.dependency_overrides.pop(sources_ctrl.get_storage, None)
        app.dependency_overrides.pop(get_current_user, None)


async def test_upload_forbidden_without_write(session, client):
    # 普通 user 对 company KB 无写权限
    user, kb = await _setup_user_kb(session, role="user")
    await session.commit()
    app.dependency_overrides[sources_ctrl.get_storage] = lambda: FakeStorage()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        r = await client.post(
            f"/api/kbs/{kb.id}/sources",
            files={"file": ("a.md", b"# hi", "text/markdown")},
        )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(sources_ctrl.get_storage, None)
        app.dependency_overrides.pop(get_current_user, None)


async def test_upload_rejects_empty_file(session, client):
    user, kb = await _setup_user_kb(session)
    await session.commit()
    app.dependency_overrides[sources_ctrl.get_storage] = lambda: FakeStorage()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        r = await client.post(
            f"/api/kbs/{kb.id}/sources",
            files={"file": ("a.md", b"", "text/markdown")},
        )
        assert r.status_code == 400
    finally:
        app.dependency_overrides.pop(sources_ctrl.get_storage, None)
        app.dependency_overrides.pop(get_current_user, None)
