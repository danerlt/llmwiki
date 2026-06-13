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


async def test_non_admin_cannot_list_users(client, session):
    token = await _token(client, session, "user")
    r = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
