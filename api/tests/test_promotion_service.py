import pytest
import pytest_asyncio

from app.repositories import kb_repo, wiki_repo
from app.services import org_service, promotion_service


@pytest_asyncio.fixture
async def setup(session):
    company = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    alice = await org_service.create_user(
        session, email="alice@x.com", password="pw123456", display_name="Alice", role="user"
    )
    await session.flush()
    alice_kb = (await kb_repo.list_by_scope(session, "personal", alice.id))[0]
    page = await wiki_repo.upsert(
        session, kb_id=alice_kb.id, slug="想法", title="好想法",
        page_type="concept", content_md="内容", frontmatter={}, source_ids=["s1"],
    )
    await session.flush()
    return {"company": company, "admin": admin, "alice": alice, "page": page}


async def test_alice_requests_admin_approves_promotes(session, setup):
    s = setup
    pr = await promotion_service.request_promotion(
        session, s["alice"], s["page"].id, s["company"].id, note="申请上公司"
    )
    await session.flush()
    assert pr.status == "pending"
    # alice（非 admin）不能审批公司 KB
    with pytest.raises(PermissionError):
        await promotion_service.approve(session, s["alice"], pr.id)
    # admin 能审批 → 页被复制到公司 KB
    await promotion_service.approve(session, s["admin"], pr.id)
    await session.flush()
    company_pages = {p.slug for p in await wiki_repo.list_by_kb(session, s["company"].id)}
    assert "想法" in company_pages
    refreshed = await promotion_service.get(session, pr.id)
    assert refreshed.status == "approved" and refreshed.reviewer_id == s["admin"].id


async def test_reviewable_filtered_by_write_permission(session, setup):
    s = setup
    await promotion_service.request_promotion(session, s["alice"], s["page"].id, s["company"].id)
    await session.flush()
    assert len(await promotion_service.list_reviewable(session, s["admin"])) == 1  # admin 可审公司
    assert await promotion_service.list_reviewable(session, s["alice"]) == []  # alice 不可审公司


async def test_cannot_request_unreadable_page(session, setup):
    s = setup
    bob = await org_service.create_user(
        session, email="bob@x.com", password="pw123456", display_name="Bob", role="user"
    )
    await session.flush()
    with pytest.raises(PermissionError):
        await promotion_service.request_promotion(session, bob, s["page"].id, s["company"].id)
