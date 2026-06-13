from app.models import AuditEvent, User


async def test_audit_event_persists(session):
    u = User(email="a@x.com", password_hash="h", display_name="A", role="admin")
    session.add(u)
    await session.flush()
    ev = AuditEvent(actor_id=u.id, action="user.create", target_type="user",
                    detail={"email": "b@x.com"})
    session.add(ev)
    await session.flush()
    assert ev.action == "user.create" and ev.detail["email"] == "b@x.com"
    assert ev.target_type == "user"
