from app.models import KnowledgeBase, User
from app.repositories import source_repo


async def _kb_user(session):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name="公司")
    u = User(email="a@x.com", password_hash="h", display_name="A", role="admin")
    session.add_all([kb, u])
    await session.flush()
    return kb, u


async def test_create_get_and_status_flow(session):
    kb, u = await _kb_user(session)
    src = await source_repo.create(
        session, kb_id=kb.id, uploader_id=u.id, filename="a.md",
        content_type="text/markdown", storage_key="k",
    )
    await session.flush()
    assert src.status == "pending"

    got = await source_repo.get_by_id(session, src.id)
    assert got is not None and got.id == src.id

    await source_repo.set_job_id(session, src.id, "job-1")
    await source_repo.set_status(session, src.id, "failed", error="boom")
    await session.flush()
    refreshed = await source_repo.get_by_id(session, src.id)
    assert refreshed.job_id == "job-1"
    assert refreshed.status == "failed" and refreshed.error == "boom"


async def test_list_by_kb(session):
    kb, u = await _kb_user(session)
    await source_repo.create(
        session, kb_id=kb.id, uploader_id=u.id, filename="a.md",
        content_type="text/markdown", storage_key="k1",
    )
    await session.flush()
    rows = await source_repo.list_by_kb(session, kb.id)
    assert len(rows) == 1
