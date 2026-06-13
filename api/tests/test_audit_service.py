from app.services import audit_service, org_service


async def test_record_and_list_recent(session):
    u = await org_service.create_user(
        session, email="a@x.com", password="pw123456", display_name="A", role="admin"
    )
    await session.flush()
    await audit_service.record(session, actor_id=u.id, action="a.one", target_type="x")
    await audit_service.record(session, actor_id=u.id, action="a.two")
    await audit_service.record(session, actor_id=u.id, action="a.three")
    await session.flush()

    actions = {e.action for e in await audit_service.list_recent(session)}
    assert {"a.one", "a.two", "a.three"} <= actions

    limited = await audit_service.list_recent(session, limit=2)
    assert len(limited) == 2  # limit 生效
