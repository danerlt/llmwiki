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


async def test_refresh_token_issues_new_access(client, session):
    await org_service.create_user(session, email="r@x.com", password="pw123456", display_name="R")
    await session.commit()
    login = await client.post("/api/auth/login", json={"email": "r@x.com", "password": "pw123456"})
    refresh_tok = login.json()["refresh_token"]
    assert refresh_tok
    # 用 refresh 换新 access
    r = await client.post("/api/auth/refresh", json={"refresh_token": refresh_tok})
    assert r.status_code == 200
    new_access = r.json()["access_token"]
    assert (
        await client.get("/api/me", headers={"Authorization": f"Bearer {new_access}"})
    ).status_code == 200
    # access 令牌不能当 refresh 用
    bad = await client.post("/api/auth/refresh", json={"refresh_token": new_access})
    assert bad.status_code == 401


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


async def test_login_lockout_after_repeated_failures(client, session):
    from app.services import auth_service

    auth_service.reset_lockout()
    await org_service.create_user(session, email="lock@x.com", password="pw123456", display_name="L")
    await session.commit()
    for _ in range(5):
        r = await client.post("/api/auth/login", json={"email": "lock@x.com", "password": "badpass"})
        assert r.status_code == 401
    # 触发锁定后即便密码正确也 429
    blocked = await client.post("/api/auth/login", json={"email": "lock@x.com", "password": "pw123456"})
    assert blocked.status_code == 429
    auth_service.reset_lockout()


async def test_me_export_returns_personal_data(client, session):
    from app.repositories import kb_repo, wiki_repo

    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    page = await wiki_repo.upsert(session, kb_id=kb.id, slug="p", title="P", page_type="concept",
                                 content_md="x", frontmatter={}, source_ids=[])
    await session.commit()
    from app.core.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        await client.post(f"/api/pages/{page.id}/comments", json={"body": "我的评论"})
        await client.post(f"/api/pages/{page.id}/favorite")
        r = await client.get("/api/me/export")
        assert r.status_code == 200
        body = r.json()
        assert body["profile"]["email"] == "admin@x.com"
        assert any(c["body"] == "我的评论" for c in body["comments"])
        assert any(f["page_id"] == str(page.id) for f in body["favorites"])
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_login_bad_password(client, session):
    await org_service.create_user(session, email="u@x.com", password="right1", display_name="U")
    await session.commit()
    r = await client.post("/api/auth/login", json={"email": "u@x.com", "password": "wrong1"})
    assert r.status_code == 401
