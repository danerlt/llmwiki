from app.models import KnowledgeBase, PromotionRequest, User, WikiPage


async def test_promotion_request_persists(session):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name="公司")
    u = User(email="a@x.com", password_hash="h", display_name="A", role="user")
    session.add_all([kb, u])
    await session.flush()
    page = WikiPage(kb_id=kb.id, title="P", slug="p", page_type="entity",
                    content_md="x", frontmatter={}, source_ids=[])
    session.add(page)
    await session.flush()
    pr = PromotionRequest(page_id=page.id, to_kb_id=kb.id, requested_by=u.id)
    session.add(pr)
    await session.flush()
    assert pr.status == "pending" and pr.reviewer_id is None
