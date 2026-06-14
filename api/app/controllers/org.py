import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import require_admin
from app.db.session import get_db
from app.models import User
from app.schemas.auth import UserOut
from app.schemas.org import (
    DepartmentCreate,
    DepartmentOut,
    TeamCreate,
    TeamMemberAdd,
    TeamOut,
    UserCreate,
)
from app.services import org_service

router = APIRouter(tags=["org"], dependencies=[Depends(require_admin)])


@router.post("/departments", response_model=Response[DepartmentOut])
@api_response
async def create_department(
    body: DepartmentCreate,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    return await org_service.create_department_for_admin(
        session, actor_id=actor.id, name=body.name, parent_id=body.parent_id
    )


@router.get("/departments", response_model=Response[list[DepartmentOut]])
@api_response
async def list_departments(session: AsyncSession = Depends(get_db)):
    return await org_service.list_departments(session)


@router.post("/teams", response_model=Response[TeamOut])
@api_response
async def create_team(
    body: TeamCreate,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    return await org_service.create_team_for_admin(session, actor_id=actor.id, name=body.name)


@router.get("/teams", response_model=Response[list[TeamOut]])
@api_response
async def list_teams(session: AsyncSession = Depends(get_db)):
    return await org_service.list_teams(session)


@router.get("/users", response_model=Response[list[UserOut]])
@api_response
async def list_users(session: AsyncSession = Depends(get_db)):
    return await org_service.list_users(session)


@router.post("/teams/{team_id}/members")
@api_response
async def add_member(
    team_id: uuid.UUID,
    body: TeamMemberAdd,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    await org_service.add_team_member(
        session, actor_id=actor.id, team_id=team_id, user_id=body.user_id, can_write=body.can_write
    )
    return {"status": "ok"}


@router.post("/users/{user_id}/deactivate", response_model=Response[UserOut])
@api_response
async def deactivate_user(
    user_id: uuid.UUID,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    return await org_service.deactivate_user(session, actor_id=actor.id, user_id=user_id)


@router.post("/users/{user_id}/activate", response_model=Response[UserOut])
@api_response
async def activate_user(
    user_id: uuid.UUID,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    return await org_service.activate_user(session, actor_id=actor.id, user_id=user_id)


@router.post("/users", response_model=Response[UserOut])
@api_response
async def create_user(
    body: UserCreate,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    return await org_service.create_user_for_admin(
        session,
        actor_id=actor.id,
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        role=body.role,
        department_id=body.department_id,
    )
