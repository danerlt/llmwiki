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
async def test_access_log_emitted_with_method_and_path(caplog):
    import logging

    transport = ASGITransport(app=app)
    with caplog.at_level(logging.INFO, logger="app.access"):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.get("/api/health")
    assert any("GET" in r.message and "/api/health" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_rate_limit_returns_429(monkeypatch):
    from app.core import middleware
    from app.core.config import settings

    monkeypatch.setattr(settings, "rate_limit_per_min", 3)
    middleware.reset_rate_limit()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # /api/kbs 非豁免路径；超过 3 次/分钟后应 429（限流在鉴权之前）
        codes = [(await ac.get("/api/kbs")).status_code for _ in range(6)]
    assert 429 in codes and codes[-1] == 429
    middleware.reset_rate_limit()


@pytest.mark.asyncio
async def test_metrics_exposes_request_counters():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.get("/api/health")
        resp = await ac.get("/api/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text
    assert "http_request_duration_seconds_count" in resp.text


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
