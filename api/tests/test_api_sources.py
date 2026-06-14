import uuid

import app.worker.queue as queue_mod
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


async def test_upload_creates_pending_source(session, client, monkeypatch):
    user, kb = await _setup_user_kb(session)
    await session.commit()

    fake_storage = FakeStorage()
    enqueued: list[str] = []

    app.dependency_overrides[sources_ctrl.get_storage] = lambda: fake_storage
    app.dependency_overrides[get_current_user] = lambda: user

    async def _fake_enqueue(source_id: str) -> str:
        enqueued.append(source_id)
        return "job-xyz"

    monkeypatch.setattr(queue_mod, "enqueue_ingest", _fake_enqueue)  # 自动还原, 防泄漏
    try:
        r = await client.post(
            f"/api/kbs/{kb.id}/sources",
            files={"file": ("a.md", b"# hi", "text/markdown")},
        )
        assert r.status_code == 200
        body = r.json()["data"]
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


async def test_upload_enqueue_failure_marks_source_failed(session, client, monkeypatch):
    user, kb = await _setup_user_kb(session)
    await session.commit()
    app.dependency_overrides[sources_ctrl.get_storage] = lambda: FakeStorage()
    app.dependency_overrides[get_current_user] = lambda: user

    async def _boom(source_id: str) -> str:
        raise RuntimeError("redis down")

    monkeypatch.setattr(queue_mod, "enqueue_ingest", _boom)
    try:
        r = await client.post(
            f"/api/kbs/{kb.id}/sources",
            files={"file": ("a.md", b"# hi", "text/markdown")},
        )
        assert r.status_code == 503
        # 不会永久卡在 pending：置 failed 可重试
        srcs = await source_repo.list_by_kb(session, kb.id)
        assert len(srcs) == 1 and srcs[0].status == "failed"
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


async def test_list_sources_returns_kb_sources(session, client):
    user, kb = await _setup_user_kb(session)
    await source_repo.create(
        session, kb_id=kb.id, uploader_id=user.id, filename="a.md",
        content_type="text/markdown", storage_key="k",
    )
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        r = await client.get(f"/api/kbs/{kb.id}/sources")
        assert r.status_code == 200
        items = r.json()["data"]
        assert len(items) == 1 and items[0]["filename"] == "a.md"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_reingest_resets_status_and_enqueues(session, client, monkeypatch):
    user, kb = await _setup_user_kb(session)
    src = await source_repo.create(
        session, kb_id=kb.id, uploader_id=user.id, filename="a.md",
        content_type="text/markdown", storage_key="k", status="failed",
    )
    await source_repo.set_status(session, src.id, "failed", error="boom")
    await session.commit()

    enqueued: list[str] = []

    async def _fake_enqueue(source_id: str) -> str:
        enqueued.append(source_id)
        return "job-re"

    monkeypatch.setattr(queue_mod, "enqueue_ingest", _fake_enqueue)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        r = await client.post(f"/api/sources/{src.id}/reingest")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["status"] == "pending" and body["error"] is None
        assert enqueued == [str(src.id)]
        refreshed = await source_repo.get_by_id(session, src.id)
        assert refreshed.status == "pending" and refreshed.job_id == "job-re"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_reingest_forbidden_without_write(session, client):
    user, kb = await _setup_user_kb(session, role="user")
    src = await source_repo.create(
        session, kb_id=kb.id, uploader_id=user.id, filename="a.md",
        content_type="text/markdown", storage_key="k",
    )
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        r = await client.post(f"/api/sources/{src.id}/reingest")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_upload_rejects_oversize_file(session, client, monkeypatch):
    from app.core.config import settings

    user, kb = await _setup_user_kb(session)
    await session.commit()
    monkeypatch.setattr(settings, "max_upload_bytes", 16)  # 调低上限便于触发
    app.dependency_overrides[sources_ctrl.get_storage] = lambda: FakeStorage()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        r = await client.post(
            f"/api/kbs/{kb.id}/sources",
            files={"file": ("a.md", b"x" * 100, "text/markdown")},
        )
        assert r.status_code == 413
        # 超限在创建 source 之前就被拒，不留垃圾记录
        assert await source_repo.list_by_kb(session, kb.id) == []
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
