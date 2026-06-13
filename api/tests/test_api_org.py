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
