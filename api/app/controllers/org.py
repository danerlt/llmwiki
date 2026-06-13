import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_db
from app.repositories import org_repo
from app.schemas.auth import UserOut
from app.schemas.org import (
    DepartmentCreate, DepartmentOut, TeamCreate, TeamMemberAdd, TeamOut, UserCreate,
)
from app.services import org_service

router = APIRouter(tags=["org"], dependencies=[Depends(require_admin)])


@router.post("/departments", response_model=DepartmentOut)
async def create_department(body: DepartmentCreate, session: AsyncSession = Depends(get_db)):
    dept = await org_service.create_department(session, name=body.name, parent_id=body.parent_id)
    await session.commit()
    return dept


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(session: AsyncSession = Depends(get_db)):
    return await org_repo.list_departments(session)


@router.post("/teams", response_model=TeamOut)
async def create_team(body: TeamCreate, session: AsyncSession = Depends(get_db)):
    team = await org_service.create_team(session, name=body.name)
    await session.commit()
    return team


@router.post("/teams/{team_id}/members")
async def add_member(team_id: uuid.UUID, body: TeamMemberAdd, session: AsyncSession = Depends(get_db)):
    await org_repo.add_team_member(session, team_id=team_id, user_id=body.user_id)
    await session.commit()
    return {"status": "ok"}


@router.post("/users", response_model=UserOut)
async def create_user(body: UserCreate, session: AsyncSession = Depends(get_db)):
    user = await org_service.create_user(
        session, email=body.email, password=body.password, display_name=body.display_name,
        role=body.role, department_id=body.department_id,
    )
    await session.commit()
    return user
