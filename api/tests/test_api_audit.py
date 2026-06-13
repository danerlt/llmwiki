from app.services import org_service


async def _token(client, session, role):
    await org_service.create_user(
        session, email=f"{role}@x.com", password="pw123456", display_name=role, role=role
    )
    await session.commit()
    r = await client.post("/api/auth/login", json={"email": f"{role}@x.com", "password": "pw123456"})
    return r.json()["access_token"]


async def test_admin_action_recorded_and_listed(client, session):
    token = await _token(client, session, "admin")
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(
        "/api/users",
        json={"email": "newbie@x.com", "password": "pw123456", "display_name": "Newbie"},
        headers=h,
    )
    assert r.status_code == 200
    audit = await client.get("/api/audit", headers=h)
    assert audit.status_code == 200
    actions = [e["action"] for e in audit.json()]
    assert "user.create" in actions  # 通过 API 建用户产生审计事件


async def test_non_admin_cannot_view_audit(client, session):
    token = await _token(client, session, "user")
    r = await client.get("/api/audit", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
