import uuid

from app.models import Department, KnowledgeBase, User


async def test_models_persist(session):
    d = Department(name="技术部")
    session.add(d)
    await session.flush()
    u = User(email="a@x.com", password_hash="h", display_name="Alice", role="user", department_id=d.id)
    session.add(u)
    await session.flush()
    kb = KnowledgeBase(scope_type="department", scope_ref_id=d.id, name="技术部 KB")
    session.add(kb)
    await session.flush()
    assert isinstance(u.id, uuid.UUID)
    assert u.department_id == d.id
    assert kb.scope_type == "department"
