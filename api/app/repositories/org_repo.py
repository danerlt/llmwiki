import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Department, Team, UserTeam
from app.repositories.base_crud import BaseCrud


class OrgRepo(BaseCrud[Department]):
    """组织架构仓储：通用增删查继承自 BaseCrud（主实体 Department），下为实体专属查询。"""

    def __init__(self) -> None:
        super().__init__(Department)

    async def create_department(
        self, session: AsyncSession, *, name: str, parent_id: uuid.UUID | None
    ) -> Department:
        dept = Department(name=name, parent_id=parent_id)
        session.add(dept)
        return dept

    async def list_departments(self, session: AsyncSession) -> list[Department]:
        res = await session.execute(select(Department))
        return list(res.scalars().all())

    async def create_team(self, session: AsyncSession, *, name: str) -> Team:
        team = Team(name=name)
        session.add(team)
        return team

    async def list_teams(self, session: AsyncSession) -> list[Team]:
        res = await session.execute(select(Team))
        return list(res.scalars().all())

    async def add_team_member(
        self, session: AsyncSession, *, team_id: uuid.UUID, user_id: uuid.UUID, can_write: bool = True
    ) -> None:
        session.add(UserTeam(team_id=team_id, user_id=user_id, can_write=can_write))

    async def ancestor_department_ids(
        self, session: AsyncSession, dept_id: uuid.UUID | None
    ) -> list[uuid.UUID]:
        if dept_id is None:
            return []
        dept = Department.__table__
        base = (
            select(dept.c.id, dept.c.parent_id)
            .where(dept.c.id == dept_id)
            .cte("anc", recursive=True)
        )
        parent = dept.alias()
        rec = select(parent.c.id, parent.c.parent_id).join(base, parent.c.id == base.c.parent_id)
        anc = base.union_all(rec)
        res = await session.execute(select(anc.c.id))
        return [r[0] for r in res.all()]


org_repo = OrgRepo()
