
from app.models import KnowledgeBase, PageLink, Source, User, WikiPage
from app.models.wiki_page import PAGE_TYPES


async def test_source_and_page_persist(session):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name="公司")
    session.add(kb)
    u = User(email="a@x.com", password_hash="h", display_name="A", role="admin")
    session.add(u)
    await session.flush()

    src = Source(
        kb_id=kb.id, uploader_id=u.id, filename="a.md",
        content_type="text/markdown", storage_key="k", status="pending",
    )
    session.add(src)
    await session.flush()
    assert src.status == "pending" and src.error is None

    page = WikiPage(
        kb_id=kb.id, title="实体A", slug="实体A", page_type="entity",
        content_md="# 实体A\n见 [[概念B]]", frontmatter={"type": "entity"},
        source_ids=[str(src.id)],
    )
    session.add(page)
    await session.flush()
    assert page.source_ids == [str(src.id)]
    assert "entity" in PAGE_TYPES

    link = PageLink(from_page_id=page.id, to_slug="概念B", to_page_id=None)
    session.add(link)
    await session.flush()
    assert link.to_page_id is None
