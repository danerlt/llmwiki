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


async def test_login_bad_password(client, session):
    await org_service.create_user(session, email="u@x.com", password="right1", display_name="U")
    await session.commit()
    r = await client.post("/api/auth/login", json={"email": "u@x.com", "password": "wrong1"})
    assert r.status_code == 401
