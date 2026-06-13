import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Department, Team, UserTeam


async def create_department(
    session: AsyncSession, *, name: str, parent_id: uuid.UUID | None
) -> Department:
    dept = Department(name=name, parent_id=parent_id)
    session.add(dept)
    return dept


async def list_departments(session: AsyncSession) -> list[Department]:
    res = await session.execute(select(Department))
    return list(res.scalars().all())


async def create_team(session: AsyncSession, *, name: str) -> Team:
    team = Team(name=name)
    session.add(team)
    return team


async def add_team_member(session: AsyncSession, *, team_id: uuid.UUID, user_id: uuid.UUID) -> None:
    session.add(UserTeam(team_id=team_id, user_id=user_id))


async def ancestor_department_ids(
    session: AsyncSession, dept_id: uuid.UUID | None
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
