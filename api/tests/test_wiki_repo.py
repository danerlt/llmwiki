from app.models import KnowledgeBase
from app.repositories import wiki_repo


async def _kb(session):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name="公司")
    session.add(kb)
    await session.flush()
    return kb


async def test_upsert_is_idempotent_by_kb_slug(session):
    kb = await _kb(session)
    p1 = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="实体A", title="实体A",
        page_type="entity", content_md="v1", frontmatter={}, source_ids=["s1"],
    )
    await session.flush()
    p2 = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="实体A", title="实体A",
        page_type="entity", content_md="v2", frontmatter={}, source_ids=["s1", "s2"],
    )
    await session.flush()
    assert p1.id == p2.id  # 同 kb+slug 复用同一行
    assert p2.content_md == "v2" and p2.source_ids == ["s1", "s2"]
    assert len(await wiki_repo.list_by_kb(session, kb.id)) == 1


async def test_replace_links_and_backfill(session):
    kb = await _kb(session)
    a = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="实体A", title="实体A",
        page_type="entity", content_md="见 [[概念B]]", frontmatter={}, source_ids=[],
    )
    await session.flush()
    await wiki_repo.replace_links(session, from_page_id=a.id, to_slugs=["概念B"])
    await session.flush()
    # 概念B 还不存在 → to_page_id 为空
    links = await wiki_repo.links_from(session, a.id)
    assert links[0].to_slug == "概念B" and links[0].to_page_id is None

    b = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="概念B", title="概念B",
        page_type="concept", content_md="x", frontmatter={}, source_ids=[],
    )
    await session.flush()
    await wiki_repo.backfill_link_targets(session, kb_id=kb.id)
    await session.flush()
    links = await wiki_repo.links_from(session, a.id)
    assert links[0].to_page_id == b.id  # 回填命中


async def test_outlinks_returns_only_resolved_targets(session):
    kb = await _kb(session)
    a = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="A", title="A",
        page_type="entity", content_md="见 [[B]] 与 [[缺失]]", frontmatter={}, source_ids=[],
    )
    b = await wiki_repo.upsert(
        session, kb_id=kb.id, slug="B", title="B",
        page_type="concept", content_md="x", frontmatter={}, source_ids=[],
    )
    await session.flush()
    await wiki_repo.replace_links(session, from_page_id=a.id, to_slugs=["B", "缺失"])
    await session.flush()
    await wiki_repo.backfill_link_targets(session, kb_id=kb.id)
    await session.flush()
    outs = await wiki_repo.outlinks(session, a.id)
    assert [o.id for o in outs] == [b.id]  # 只含已解析目标，未解析的「缺失」不出现
