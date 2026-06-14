from app.services import org_service


async def test_login_and_me(client, session):
    await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin",
    )
    await session.commit()

    r = await client.post("/api/auth/login", json={"email": "admin@x.com", "password": "pw123456"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r2 = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["email"] == "admin@x.com"


async def test_logout_revokes_existing_token(client, session):
    await org_service.create_user(session, email="u@x.com", password="pw123456", display_name="U")
    await session.commit()
    token = (
        await client.post("/api/auth/login", json={"email": "u@x.com", "password": "pw123456"})
    ).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/api/me", headers=auth)).status_code == 200
    # 登出自增 token_version → 旧令牌立即失效
    assert (await client.post("/api/auth/logout", headers=auth)).status_code == 204
    assert (await client.get("/api/me", headers=auth)).status_code == 401


async def test_change_password_rotates_sessions(client, session):
    await org_service.create_user(session, email="u@x.com", password="pw123456", display_name="U")
    await session.commit()
    old = (
        await client.post("/api/auth/login", json={"email": "u@x.com", "password": "pw123456"})
    ).json()["access_token"]
    oldh = {"Authorization": f"Bearer {old}"}
    # 错误旧密码 → 400
    bad = await client.post(
        "/api/auth/change-password",
        json={"old_password": "wrongxx", "new_password": "newpass123"},
        headers=oldh,
    )
    assert bad.status_code == 400
    # 正确改密 → 返回新令牌
    ok = await client.post(
        "/api/auth/change-password",
        json={"old_password": "pw123456", "new_password": "newpass123"},
        headers=oldh,
    )
    assert ok.status_code == 200
    newtok = ok.json()["access_token"]
    # 旧令牌失效，新令牌可用
    assert (await client.get("/api/me", headers=oldh)).status_code == 401
    assert (
        await client.get("/api/me", headers={"Authorization": f"Bearer {newtok}"})
    ).status_code == 200
    # 新密码可登录
    assert (
        await client.post("/api/auth/login", json={"email": "u@x.com", "password": "newpass123"})
    ).status_code == 200


async def test_login_bad_password(client, session):
    await org_service.create_user(session, email="u@x.com", password="right1", display_name="U")
    await session.commit()
    r = await client.post("/api/auth/login", json={"email": "u@x.com", "password": "wrong1"})
    assert r.status_code == 401
