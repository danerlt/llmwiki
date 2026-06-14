from app.core.deps import get_current_user
from app.main import app
from app.services import org_service, webhook_service


def test_sign_is_deterministic_hmac():
    s1 = webhook_service.sign("secret", b"body")
    s2 = webhook_service.sign("secret", b"body")
    assert s1 == s2 and len(s1) == 64  # sha256 hex
    assert webhook_service.sign("other", b"body") != s1


async def test_dispatch_noop_without_webhooks(session):
    # 无注册 webhook 时不应发起任何 HTTP（不抛异常即通过）
    await webhook_service.dispatch(session, "page.updated", {"x": 1})


async def test_webhook_crud_admin_only(session, client):
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    user = await org_service.create_user(
        session, email="u@x.com", password="pw123456", display_name="U", role="user"
    )
    await session.commit()

    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        r = await client.post(
            "/api/webhooks", json={"url": "https://example.com/hook", "secret": "supersecret"}
        )
        assert r.status_code == 201
        wid = r.json()["data"]["id"]
        assert "secret" not in r.json()["data"]  # 不回显密钥
        assert len((await client.get("/api/webhooks")).json()["data"]) == 1
        assert (await client.delete(f"/api/webhooks/{wid}")).status_code == 204
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        assert (await client.get("/api/webhooks")).status_code == 403  # 非 admin
    finally:
        app.dependency_overrides.pop(get_current_user, None)
