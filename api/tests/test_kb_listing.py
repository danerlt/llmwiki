from app.repositories import org_repo
from app.services import kb_service, org_service


async def test_kb_listing_filtered_by_permission(client, session):
    tech = await org_repo.create_department(session, name="技术部", parent_id=None)
    await session.flush()
    backend = await org_repo.create_department(session, name="后端组", parent_id=tech.id)
    frontend = await org_repo.create_department(session, name="前端组", parent_id=tech.id)
    await session.flush()
    await kb_service.ensure_kb(session, "company", None, "公司")
    await kb_service.ensure_kb(session, "department", tech.id, "技术部")
    await kb_service.ensure_kb(session, "department", backend.id, "后端组")
    await kb_service.ensure_kb(session, "department", frontend.id, "前端组")
    alice = await org_service.create_user(
        session, email="alice@x.com", password="pw123456", display_name="Alice", department_id=backend.id,
    )
    await session.commit()

    r = await client.post("/api/auth/login", json={"email": "alice@x.com", "password": "pw123456"})
    token = r.json()["data"]["access_token"]
    r2 = await client.get("/api/kbs", headers={"Authorization": f"Bearer {token}"})
    body = r2.json()
    # 阶段3 灰度：/api/kbs 改走统一信封 Response[T]
    assert body["success"] is True and body["code"] == "0"
    assert body["request_id"]
    names = {kb["name"] for kb in body["data"]}
    assert names == {"公司", "技术部", "后端组", "Alice 个人"}
    assert "前端组" not in names
