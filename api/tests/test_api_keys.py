from app.core.deps import get_current_user
from app.main import app
from app.services import org_service


async def test_api_key_create_use_revoke(session, client):
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    await session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        created = await client.post("/api/api-keys", json={"name": "ci-bot"})
        assert created.status_code == 201
        raw = created.json()["data"]["key"]
        assert raw.startswith("lk_")
        kid = created.json()["data"]["id"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 用 API Key（无 JWT override）访问受保护端点 → 以 owner 身份通过
    me = await client.get("/api/me", headers={"X-API-Key": raw})
    assert me.status_code == 200 and me.json()["data"]["email"] == "admin@x.com"

    # 无效 key → 401
    assert (await client.get("/api/me", headers={"X-API-Key": "lk_bad_key"})).status_code == 401

    # 吊销后失效
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        assert (await client.delete(f"/api/api-keys/{kid}")).status_code == 204
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert (await client.get("/api/me", headers={"X-API-Key": raw})).status_code == 401


async def test_no_auth_returns_401(session, client):
    # 既无 JWT 也无 API Key
    assert (await client.get("/api/me")).status_code == 401
