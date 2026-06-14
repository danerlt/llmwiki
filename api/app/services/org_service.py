import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Department, Team, User
from app.repositories import org_repo, user_repo
from app.services.kb_service import kb_service


class OrgService:
    async def create_department(
        self, session: AsyncSession, *, name: str, parent_id: uuid.UUID | None
    ) -> Department:
        dept = await org_repo.create_department(session, name=name, parent_id=parent_id)
        await session.flush()
        await kb_service.ensure_kb(session, "department", dept.id, name)
        return dept

    async def create_team(self, session: AsyncSession, *, name: str) -> Team:
        team = await org_repo.create_team(session, name=name)
        await session.flush()
        await kb_service.ensure_kb(session, "team", team.id, name)
        return team

    async def create_user(
        self, session: AsyncSession, *, email: str, password: str, display_name: str,
        role: str = "user", department_id: uuid.UUID | None = None,
    ) -> User:
        user = await user_repo.create(
            session, email=email, password_hash=hash_password(password),
            display_name=display_name, role=role, department_id=department_id,
        )
        await session.flush()
        await kb_service.ensure_kb(session, "personal", user.id, f"{display_name} 个人")
        return user


org_service = OrgService()
