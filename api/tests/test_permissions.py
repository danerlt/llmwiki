import pytest
import pytest_asyncio

from app.repositories import kb_repo, org_repo, user_repo
from app.services import kb_service, permission_service


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def org(session):
    tech = await org_repo.create_department(session, name="技术部", parent_id=None)
    await session.flush()
    backend = await org_repo.create_department(session, name="后端组", parent_id=tech.id)
    frontend = await org_repo.create_department(session, name="前端组", parent_id=tech.id)
    product = await org_repo.create_department(session, name="产品部", parent_id=None)
    await session.flush()

    projx = await org_repo.create_team(session, name="项目X")
    await session.flush()

    admin = await user_repo.create(session, email="admin@x.com", password_hash="h", display_name="Admin", role="admin", department_id=tech.id)
    alice = await user_repo.create(session, email="alice@x.com", password_hash="h", display_name="Alice", role="user", department_id=backend.id)
    bob = await user_repo.create(session, email="bob@x.com", password_hash="h", display_name="Bob", role="user", department_id=frontend.id)
    carol = await user_repo.create(session, email="carol@x.com", password_hash="h", display_name="Carol", role="user", department_id=product.id)
    await session.flush()

    await org_repo.add_team_member(session, team_id=projx.id, user_id=alice.id)
    await org_repo.add_team_member(session, team_id=projx.id, user_id=carol.id)

    company_kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await kb_service.ensure_kb(session, "department", tech.id, "技术部")
    await kb_service.ensure_kb(session, "department", backend.id, "后端组")
    await kb_service.ensure_kb(session, "department", frontend.id, "前端组")
    await kb_service.ensure_kb(session, "department", product.id, "产品部")
    await kb_service.ensure_kb(session, "team", projx.id, "项目X")
    for u in (admin, alice, bob, carol):
        await kb_service.ensure_kb(session, "personal", u.id, f"{u.display_name} 个人")
    await session.flush()

    return {
        "tech": tech, "backend": backend, "frontend": frontend, "product": product,
        "projx": projx, "admin": admin, "alice": alice, "bob": bob, "carol": carol,
        "company_kb": company_kb,
    }


async def _kb_names(session, ids):
    rows = await kb_repo.list_by_ids(session, list(ids))
    return {r.name for r in rows}


async def test_alice_sees_ancestors_and_team_not_siblings(session, org):
    ids = await permission_service.accessible_kb_ids(session, org["alice"])
    names = await _kb_names(session, ids)
    assert names == {"公司", "技术部", "后端组", "项目X", "Alice 个人"}
    assert "前端组" not in names
    assert "Bob 个人" not in names
    assert "产品部" not in names


async def test_bob_not_in_team_cannot_see_team_kb(session, org):
    ids = await permission_service.accessible_kb_ids(session, org["bob"])
    names = await _kb_names(session, ids)
    assert names == {"公司", "技术部", "前端组", "Bob 个人"}
    assert "项目X" not in names
    assert "后端组" not in names


async def test_can_write_rules(session, org):
    company_kb = org["company_kb"]
    tech_kb = (await kb_repo.list_by_scope(session, "department", org["tech"].id))[0]
    projx_kb = (await kb_repo.list_by_scope(session, "team", org["projx"].id))[0]
    alice_kb = (await kb_repo.list_by_scope(session, "personal", org["alice"].id))[0]
    bob_kb = (await kb_repo.list_by_scope(session, "personal", org["bob"].id))[0]

    assert await permission_service.can_write(session, org["admin"], company_kb) is True
    assert await permission_service.can_write(session, org["admin"], tech_kb) is True
    assert await permission_service.can_write(session, org["alice"], tech_kb) is False
    assert await permission_service.can_write(session, org["alice"], alice_kb) is True
    assert await permission_service.can_write(session, org["alice"], projx_kb) is True
    assert await permission_service.can_write(session, org["alice"], bob_kb) is False
