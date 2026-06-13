import pytest
import pytest_asyncio

from app.repositories import kb_repo, org_repo, promotion_repo, wiki_repo
from app.services import org_service, promotion_service


async def _sibling_depts(session):
    """两个平级根部门 + 各自部门 KB，互不可见。"""
    product = await org_repo.create_department(session, name="产品部", parent_id=None)
    tech = await org_repo.create_department(session, name="技术部", parent_id=None)
    await session.flush()
    product_kb = await kb_repo.create(
        session, scope_type="department", scope_ref_id=product.id, name="产品部"
    )
    tech_kb = await kb_repo.create(
        session, scope_type="department", scope_ref_id=tech.id, name="技术部"
    )
    await session.flush()
    return product, tech, product_kb, tech_kb


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


async def test_cannot_promote_into_inaccessible_target(session):
    """铁律：不能把内容晋升进自己都看不到的平级作用域 KB（跨作用域投送/泄漏）。"""
    product, tech, product_kb, tech_kb = await _sibling_depts(session)
    carol = await org_service.create_user(
        session, email="carol@x.com", password="pw123456", display_name="Carol",
        role="user", department_id=product.id,
    )
    await session.flush()
    page = await wiki_repo.upsert(
        session, kb_id=product_kb.id, slug="私密", title="产品机密",
        page_type="concept", content_md="机密内容", frontmatter={}, source_ids=[],
    )
    await session.flush()
    # 技术部 KB 不在 carol 可见集 → 拒绝晋升
    with pytest.raises(PermissionError):
        await promotion_service.request_promotion(session, carol, page.id, tech_kb.id)


async def test_approve_rejects_request_violating_requester_scope(session):
    """纵深防御：绕过 request_promotion 造出的跨作用域脏请求，审批阶段仍按申请人可见域拦截。"""
    product, tech, product_kb, tech_kb = await _sibling_depts(session)
    carol = await org_service.create_user(
        session, email="carol2@x.com", password="pw123456", display_name="Carol",
        role="user", department_id=product.id,
    )
    gadmin = await org_service.create_user(
        session, email="ga@x.com", password="pw123456", display_name="GA", role="admin"
    )
    await session.flush()
    page = await wiki_repo.upsert(
        session, kb_id=product_kb.id, slug="私密2", title="产品机密",
        page_type="concept", content_md="机密内容", frontmatter={}, source_ids=[],
    )
    await session.flush()
    # 直接造一个 carol→技术部 的脏请求（模拟历史数据/作用域漂移）
    pr = await promotion_repo.create(
        session, page_id=page.id, to_kb_id=tech_kb.id, requested_by=carol.id, note=None
    )
    await session.flush()
    # 全局 admin 虽能写技术部，但申请人 carol 读不到技术部 → 拦截，机密不会被搬进技术部
    with pytest.raises(PermissionError):
        await promotion_service.approve(session, gadmin, pr.id)
    tech_pages = {p.slug for p in await wiki_repo.list_by_kb(session, tech_kb.id)}
    assert "私密2" not in tech_pages
