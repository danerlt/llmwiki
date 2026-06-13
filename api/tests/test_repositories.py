import pytest
from app.repositories import kb_repo, org_repo, user_repo


pytestmark = pytest.mark.asyncio


async def test_user_repo_get_by_email(session):
    u = await user_repo.create(session, email="a@x.com", password_hash="h", display_name="A", role="user", department_id=None)
    await session.flush()
    found = await user_repo.get_by_email(session, "a@x.com")
    assert found is not None and found.id == u.id
    assert await user_repo.get_by_email(session, "none@x.com") is None


async def test_org_repo_department_tree(session):
    root = await org_repo.create_department(session, name="技术部", parent_id=None)
    await session.flush()
    child = await org_repo.create_department(session, name="后端组", parent_id=root.id)
    await session.flush()
    anc = await org_repo.ancestor_department_ids(session, child.id)
    assert set(anc) == {root.id, child.id}


async def test_kb_repo_create_and_list(session):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司 KB")
    await session.flush()
    rows = await kb_repo.list_by_scope(session, "company", None)
    assert kb.id in [r.id for r in rows]
