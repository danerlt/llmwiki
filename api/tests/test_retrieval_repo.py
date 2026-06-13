from app.models import KnowledgeBase
from app.repositories import wiki_repo


async def _kb(session, name="公司"):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name=name)
    session.add(kb)
    await session.flush()
    return kb


async def test_search_pages_matches_title_and_body_and_skips_index(session):
    kb = await _kb(session)
    await wiki_repo.upsert(session, kb_id=kb.id, slug="后端", title="后端",
                           page_type="entity", content_md="负责服务端", frontmatter={}, source_ids=[])
    await wiki_repo.upsert(session, kb_id=kb.id, slug="前端", title="前端",
                           page_type="entity", content_md="提到后端协作", frontmatter={}, source_ids=[])
    await wiki_repo.upsert(session, kb_id=kb.id, slug="index", title="目录",
                           page_type="index", content_md="后端 前端", frontmatter={}, source_ids=[])
    await session.flush()
    hits = await wiki_repo.search_pages(session, [kb.id], "后端", limit=10)
    slugs = [p.slug for p in hits]
    assert "后端" in slugs and "前端" in slugs   # 标题命中 + 正文命中
    assert "index" not in slugs                  # index 不作为种子
    assert hits[0].slug == "后端"                # 标题命中排前


async def test_linked_pages_returns_resolved_targets(session):
    kb = await _kb(session)
    a = await wiki_repo.upsert(session, kb_id=kb.id, slug="a", title="A",
                               page_type="entity", content_md="见 [[b]]", frontmatter={}, source_ids=[])
    b = await wiki_repo.upsert(session, kb_id=kb.id, slug="b", title="B",
                               page_type="concept", content_md="x", frontmatter={}, source_ids=[])
    await session.flush()
    await wiki_repo.replace_links(session, from_page_id=a.id, to_slugs=["b"])
    await session.flush()
    await wiki_repo.backfill_link_targets(session, kb_id=kb.id)
    await session.flush()
    linked = await wiki_repo.linked_pages(session, [a.id])
    assert [p.id for p in linked] == [b.id]


async def test_list_by_kbs(session):
    kb1 = await _kb(session, "kb1")
    kb2 = await _kb(session, "kb2")
    await wiki_repo.upsert(session, kb_id=kb1.id, slug="p1", title="P1",
                           page_type="entity", content_md="", frontmatter={}, source_ids=[])
    await wiki_repo.upsert(session, kb_id=kb2.id, slug="p2", title="P2",
                           page_type="entity", content_md="", frontmatter={}, source_ids=[])
    await session.flush()
    pages = await wiki_repo.list_by_kbs(session, [kb1.id, kb2.id])
    assert {p.slug for p in pages} == {"p1", "p2"}
