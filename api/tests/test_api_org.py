from app.services import org_service


async def _token(client, session, role):
    await org_service.create_user(session, email=f"{role}@x.com", password="pw123456", display_name=role, role=role)
    await session.commit()
    r = await client.post("/api/auth/login", json={"email": f"{role}@x.com", "password": "pw123456"})
    return r.json()["access_token"]


async def test_admin_can_create_department(client, session):
    token = await _token(client, session, "admin")
    r = await client.post("/api/departments", json={"name": "技术部"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["name"] == "技术部"


async def test_overlong_name_rejected_as_422(client, session):
    # 超过 DB 列长度的输入应在请求边界以 422 拒绝，而非穿透到 DB 抛 500
    token = await _token(client, session, "admin")
    r = await client.post(
        "/api/departments", json={"name": "长" * 300},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


async def test_non_admin_forbidden(client, session):
    token = await _token(client, session, "user")
    r = await client.post("/api/departments", json={"name": "X"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


async def test_admin_lists_teams_and_users(client, session):
    token = await _token(client, session, "admin")
    await client.post("/api/teams", json={"name": "项目X"}, headers={"Authorization": f"Bearer {token}"})
    r = await client.get("/api/teams", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and any(t["name"] == "项目X" for t in r.json())
    r2 = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200 and any(u["role"] == "admin" for u in r2.json())


async def test_admin_deactivate_blocks_user_then_activate(client, session):
    admin_token = await _token(client, session, "admin")
    h = {"Authorization": f"Bearer {admin_token}"}
    # 建一个普通用户并登录拿其令牌
    await org_service.create_user(session, email="bob@x.com", password="pw123456", display_name="Bob")
    await session.commit()
    bob_login = await client.post("/api/auth/login", json={"email": "bob@x.com", "password": "pw123456"})
    bob_tok = bob_login.json()["access_token"]
    bobh = {"Authorization": f"Bearer {bob_tok}"}
    # bob 当前可访问
    assert (await client.get("/api/me", headers=bobh)).status_code == 200
    bob_id = bob_login.json()  # noqa: F841
    bob_uid = (await client.get("/api/me", headers=bobh)).json()["id"]
    # admin 停用 bob
    d = await client.post(f"/api/users/{bob_uid}/deactivate", headers=h)
    assert d.status_code == 200 and d.json()["is_active"] is False
    # bob 旧令牌失效，且无法重新登录
    assert (await client.get("/api/me", headers=bobh)).status_code == 401
    relogin = await client.post("/api/auth/login", json={"email": "bob@x.com", "password": "pw123456"})
    new_tok = relogin.json()["access_token"]
    assert (await client.get("/api/me", headers={"Authorization": f"Bearer {new_tok}"})).status_code == 401
    # admin 不能停用自己
    me_id = (await client.get("/api/users", headers=h)).json()
    admin_uid = next(u["id"] for u in me_id if u["role"] == "admin")
    assert (await client.post(f"/api/users/{admin_uid}/deactivate", headers=h)).status_code == 400
    # 重新启用 bob → 可再次登录
    a = await client.post(f"/api/users/{bob_uid}/activate", headers=h)
    assert a.status_code == 200 and a.json()["is_active"] is True
    ok = await client.post("/api/auth/login", json={"email": "bob@x.com", "password": "pw123456"})
    assert (await client.get("/api/me", headers={"Authorization": f"Bearer {ok.json()['access_token']}"})).status_code == 200


async def test_non_admin_cannot_list_users(client, session):
    token = await _token(client, session, "user")
    r = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
