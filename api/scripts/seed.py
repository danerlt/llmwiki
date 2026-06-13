import asyncio

from app.db.session import SessionLocal
from app.repositories import user_repo
from app.services import kb_service, org_service


async def seed() -> None:
    async with SessionLocal() as session:
        if await user_repo.get_by_email(session, "admin@llmwiki.local"):
            print("already seeded")
            return
        await kb_service.ensure_kb(session, "company", None, "公司")
        tech = await org_service.create_department(session, name="技术部", parent_id=None)
        backend = await org_service.create_department(session, name="后端组", parent_id=tech.id)
        await org_service.create_department(session, name="前端组", parent_id=tech.id)
        await org_service.create_user(
            session, email="admin@llmwiki.local", password="admin12345",
            display_name="管理员", role="admin", department_id=tech.id,
        )
        await org_service.create_user(
            session, email="alice@llmwiki.local", password="alice12345",
            display_name="Alice", role="user", department_id=backend.id,
        )
        await session.commit()
        print("seeded: admin@llmwiki.local / admin12345")


if __name__ == "__main__":
    asyncio.run(seed())
