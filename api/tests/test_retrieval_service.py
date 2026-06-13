import pytest_asyncio

from app.repositories import kb_repo, org_repo, wiki_repo
from app.services import org_service, retrieval_service
from app.services.retrieval_service import _query_terms, make_snippet


def test_make_snippet_centers_on_match():
    text = "前言部分。后端使用 FastAPI 构建高性能接口，配合数据库。结尾部分。"
    snip, matched = make_snippet(text, _query_terms("FastAPI"), width=24)
    assert "FastAPI" in snip and matched.lower() == "fastapi"


@pytest_asyncio.fixture
async def org(session):
    tech = await org_repo.create_department(session, name="技术部", parent_id=None)
    await session.flush()
    backend = await org_repo.create_department(session, name="后端组", parent_id=tech.id)
    frontend = await org_repo.create_department(session, name="前端组", parent_id=tech.id)
    await session.flush()
    company_kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    tech_kb = await kb_repo.create(session, scope_type="department", scope_ref_id=tech.id, name="技术部")
    backend_kb = await kb_repo.create(session, scope_type="department", scope_ref_id=backend.id, name="后端组")
    frontend_kb = await kb_repo.create(session, scope_type="department", scope_ref_id=frontend.id, name="前端组")
    await session.flush()
    alice = await org_service.create_user(
        session, email="alice@x.com", password="pw123456", display_name="Alice",
        department_id=backend.id,
    )
    await session.flush()
    for kb in (company_kb, tech_kb, backend_kb, frontend_kb):
        await wiki_repo.upsert(session, kb_id=kb.id, slug=f"p-{kb.id}", title="后端话题",
                               page_type="entity", content_md="讲后端", frontmatter={}, source_ids=[])
    await session.flush()
    return {"alice": alice, "frontend_kb": frontend_kb, "backend_kb": backend_kb}


async def test_retrieve_never_returns_inaccessible_kb(session, org):
    pages = await retrieval_service.retrieve(session, org["alice"], "后端")
    kb_ids = {p.kb_id for p in pages}
    assert org["frontend_kb"].id not in kb_ids   # 平级前端组不可见——铁律
    assert org["backend_kb"].id in kb_ids         # 本部门可见
    assert pages, "应召回到可见 KB 的页"


async def test_graph_expansion_pulls_linked_pages(session):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="Admin", role="admin"
    )
    await session.flush()
    a = await wiki_repo.upsert(session, kb_id=kb.id, slug="种子", title="种子页",
                               page_type="entity", content_md="关键词X，见 [[相关]]",
                               frontmatter={}, source_ids=[])
    await wiki_repo.upsert(session, kb_id=kb.id, slug="相关", title="相关页",
                           page_type="concept", content_md="无关键词", frontmatter={}, source_ids=[])
    await session.flush()
    await wiki_repo.replace_links(session, from_page_id=a.id, to_slugs=["相关"])
    await session.flush()
    await wiki_repo.backfill_link_targets(session, kb_id=kb.id)
    await session.flush()
    pages = await retrieval_service.retrieve(session, admin, "关键词X")
    slugs = {p.slug for p in pages}
    assert "种子" in slugs and "相关" in slugs   # 图扩展拉入直接链接页（虽不含关键词）


async def test_retrieve_caps_result_and_prioritizes_seed(session):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="admin@x.com", password="pw123456", display_name="A", role="admin"
    )
    await session.flush()
    for i in range(20):  # 20 个共享同一 source 的页，仅一个标题含关键词
        await wiki_repo.upsert(
            session, kb_id=kb.id, slug=f"p{i}",
            title="关键词页" if i == 0 else f"页{i}",
            page_type="concept", content_md="关键词" if i == 0 else "其它",
            frontmatter={}, source_ids=["s1"],
        )
    await session.flush()
    pages = await retrieval_service.retrieve(session, admin, "关键词")
    assert len(pages) <= 8  # 共享源不再把全部 20 页拉入，总量受 cap 约束
    assert any(p.title == "关键词页" for p in pages)  # 关键词种子被优先保留


async def test_retrieve_handles_natural_language_question(session):
    kb = await kb_repo.create(session, scope_type="company", scope_ref_id=None, name="公司")
    await session.flush()
    admin = await org_service.create_user(
        session, email="a@x.com", password="pw123456", display_name="A", role="admin"
    )
    await session.flush()
    await wiki_repo.upsert(session, kb_id=kb.id, slug="后端服务", title="后端服务",
                           page_type="concept", content_md="使用 Python 与 FastAPI 构建",
                           frontmatter={}, source_ids=[])
    await session.flush()
    # 整句以前按子串召不回；现在按词(python / 后端)召回
    pages = await retrieval_service.retrieve(session, admin, "Python后端有哪些")
    assert any(p.slug == "后端服务" for p in pages)
