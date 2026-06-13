import pytest
from httpx import ASGITransport, AsyncClient

from app.controllers import health as health_ctrl
from app.main import app


@pytest.mark.asyncio
async def test_health_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_response_has_request_id_and_security_headers():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/health")
    assert resp.headers.get("X-Request-ID")  # 自动生成
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"


@pytest.mark.asyncio
async def test_incoming_request_id_is_propagated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/health", headers={"X-Request-ID": "trace-abc"})
    assert resp.headers.get("X-Request-ID") == "trace-abc"


@pytest.mark.asyncio
async def test_readyz_ok_when_all_deps_up(monkeypatch):
    monkeypatch.setattr(health_ctrl, "_check_db", lambda: _true())
    monkeypatch.setattr(health_ctrl, "_check_redis", lambda: _true())
    monkeypatch.setattr(health_ctrl, "_check_minio", lambda: _true())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"ready": True, "checks": {"db": True, "redis": True, "minio": True}}


@pytest.mark.asyncio
async def test_readyz_503_when_dep_down(monkeypatch):
    monkeypatch.setattr(health_ctrl, "_check_db", lambda: _true())
    monkeypatch.setattr(health_ctrl, "_check_redis", lambda: _false())
    monkeypatch.setattr(health_ctrl, "_check_minio", lambda: _true())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/readyz")
    assert resp.status_code == 503
    assert resp.json()["ready"] is False
    assert resp.json()["checks"]["redis"] is False


async def _true() -> bool:
    return True


async def _false() -> bool:
    return False
