from app.services import org_service


async def _token(client, session, role):
    await org_service.create_user(
        session, email=f"{role}@x.com", password="pw123456", display_name=role, role=role
    )
    await session.commit()
    r = await client.post("/api/auth/login", json={"email": f"{role}@x.com", "password": "pw123456"})
    return r.json()["data"]["access_token"]


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
    body = audit.json()["data"]
    assert body["total"] >= 1 and "items" in body
    actions = [e["action"] for e in body["items"]]
    assert "user.create" in actions  # 通过 API 建用户产生审计事件


async def test_audit_pagination_and_filter(client, session):
    token = await _token(client, session, "admin")
    h = {"Authorization": f"Bearer {token}"}
    # 产生多条事件
    for i in range(3):
        await client.post(
            "/api/users",
            json={"email": f"u{i}@x.com", "password": "pw123456", "display_name": f"U{i}"},
            headers=h,
        )
    # 分页：limit=2 只回 2 条，total 反映全部
    r = await client.get("/api/audit?limit=2&offset=0", headers=h)
    body = r.json()["data"]
    assert len(body["items"]) == 2 and body["total"] >= 3 and body["limit"] == 2
    # 动作过滤
    r2 = await client.get("/api/audit?action=user.create", headers=h)
    assert all(e["action"] == "user.create" for e in r2.json()["data"]["items"])


async def test_audit_csv_export(client, session):
    token = await _token(client, session, "admin")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/users",
        json={"email": "x@x.com", "password": "pw123456", "display_name": "X"},
        headers=h,
    )
    r = await client.get("/api/audit/export", headers=h)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "created_at,actor_email,action" in r.text
    assert "user.create" in r.text


async def test_non_admin_cannot_view_audit(client, session):
    token = await _token(client, session, "user")
    r = await client.get("/api/audit", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
