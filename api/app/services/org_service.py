import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundException, ParamsException
from app.core.security import hash_password
from app.models import Department, Team, User
from app.repositories import org_repo, user_repo
from app.schemas.auth import UserOut
from app.schemas.org import DepartmentOut, TeamOut
from app.services.audit_service import audit_service
from app.services.kb_service import kb_service


class OrgService:
    async def create_department(self, session: AsyncSession, *, name: str, parent_id: uuid.UUID | None) -> Department:
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
        self,
        session: AsyncSession,
        *,
        email: str,
        password: str,
        display_name: str,
        role: str = "user",
        department_id: uuid.UUID | None = None,
    ) -> User:
        user = await user_repo.create(
            session,
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            role=role,
            department_id=department_id,
        )
        await session.flush()
        await kb_service.ensure_kb(session, "personal", user.id, f"{display_name} 个人")
        return user

    # ---- 控制器端点编排（含审计/提交/ORM→schema 转换） ----

    async def create_department_for_admin(
        self,
        session: AsyncSession,
        *,
        actor_id: uuid.UUID,
        name: str,
        parent_id: uuid.UUID | None,
    ) -> DepartmentOut:
        dept = await self.create_department(session, name=name, parent_id=parent_id)
        await audit_service.record(
            session,
            actor_id=actor_id,
            action="department.create",
            target_type="department",
            target_id=dept.id,
            detail={"name": name},
        )
        await session.commit()
        return DepartmentOut.model_validate(dept)

    async def list_departments(self, session: AsyncSession) -> list[DepartmentOut]:
        rows = await org_repo.list_departments(session)
        return [DepartmentOut.model_validate(r) for r in rows]

    async def create_team_for_admin(self, session: AsyncSession, *, actor_id: uuid.UUID, name: str) -> TeamOut:
        team = await self.create_team(session, name=name)
        await audit_service.record(
            session,
            actor_id=actor_id,
            action="team.create",
            target_type="team",
            target_id=team.id,
            detail={"name": name},
        )
        await session.commit()
        return TeamOut.model_validate(team)

    async def list_teams(self, session: AsyncSession) -> list[TeamOut]:
        rows = await org_repo.list_teams(session)
        return [TeamOut.model_validate(r) for r in rows]

    async def list_users(self, session: AsyncSession) -> list[UserOut]:
        rows = await user_repo.list_all(session)
        return [UserOut.model_validate(r) for r in rows]

    async def add_team_member(
        self,
        session: AsyncSession,
        *,
        actor_id: uuid.UUID,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
        can_write: bool,
    ) -> None:
        await org_repo.add_team_member(session, team_id=team_id, user_id=user_id, can_write=can_write)
        await audit_service.record(
            session,
            actor_id=actor_id,
            action="team.add_member",
            target_type="team",
            target_id=team_id,
            detail={"user_id": str(user_id), "can_write": can_write},
        )
        await session.commit()

    async def deactivate_user(self, session: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID) -> UserOut:
        if user_id == actor_id:
            raise ParamsException("不能停用自己")
        target = await user_repo.get_by_id(session, user_id)
        if target is None:
            raise NotFoundException("user not found")
        await user_repo.set_active(session, user_id, False)
        await user_repo.bump_token_version(session, user_id)  # 立即切断其所有会话
        await audit_service.record(
            session, actor_id=actor_id, action="user.deactivate", target_type="user", target_id=user_id
        )
        await session.commit()
        updated = await user_repo.get_by_id(session, user_id)
        return UserOut.model_validate(updated)

    async def activate_user(self, session: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID) -> UserOut:
        target = await user_repo.get_by_id(session, user_id)
        if target is None:
            raise NotFoundException("user not found")
        await user_repo.set_active(session, user_id, True)
        await audit_service.record(
            session, actor_id=actor_id, action="user.activate", target_type="user", target_id=user_id
        )
        await session.commit()
        updated = await user_repo.get_by_id(session, user_id)
        return UserOut.model_validate(updated)

    async def create_user_for_admin(
        self,
        session: AsyncSession,
        *,
        actor_id: uuid.UUID,
        email: str,
        password: str,
        display_name: str,
        role: str = "user",
        department_id: uuid.UUID | None = None,
    ) -> UserOut:
        user = await self.create_user(
            session,
            email=email,
            password=password,
            display_name=display_name,
            role=role,
            department_id=department_id,
        )
        await audit_service.record(
            session,
            actor_id=actor_id,
            action="user.create",
            target_type="user",
            target_id=user.id,
            detail={"email": email, "role": role},
        )
        await session.commit()
        return UserOut.model_validate(user)


org_service = OrgService()
