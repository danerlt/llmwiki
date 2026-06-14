import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_db
from app.models import User
from app.repositories import org_repo, user_repo
from app.schemas.auth import UserOut
from app.schemas.org import (
    DepartmentCreate,
    DepartmentOut,
    TeamCreate,
    TeamMemberAdd,
    TeamOut,
    UserCreate,
)
from app.services import audit_service, org_service

router = APIRouter(tags=["org"], dependencies=[Depends(require_admin)])


@router.post("/departments", response_model=DepartmentOut)
async def create_department(
    body: DepartmentCreate,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    dept = await org_service.create_department(session, name=body.name, parent_id=body.parent_id)
    await audit_service.record(session, actor_id=actor.id, action="department.create",
                               target_type="department", target_id=dept.id, detail={"name": body.name})
    await session.commit()
    return dept


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(session: AsyncSession = Depends(get_db)):
    return await org_repo.list_departments(session)


@router.post("/teams", response_model=TeamOut)
async def create_team(
    body: TeamCreate,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    team = await org_service.create_team(session, name=body.name)
    await audit_service.record(session, actor_id=actor.id, action="team.create",
                               target_type="team", target_id=team.id, detail={"name": body.name})
    await session.commit()
    return team


@router.get("/teams", response_model=list[TeamOut])
async def list_teams(session: AsyncSession = Depends(get_db)):
    return await org_repo.list_teams(session)


@router.get("/users", response_model=list[UserOut])
async def list_users(session: AsyncSession = Depends(get_db)):
    return await user_repo.list_all(session)


@router.post("/teams/{team_id}/members")
async def add_member(
    team_id: uuid.UUID,
    body: TeamMemberAdd,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    await org_repo.add_team_member(
        session, team_id=team_id, user_id=body.user_id, can_write=body.can_write
    )
    await audit_service.record(session, actor_id=actor.id, action="team.add_member",
                               target_type="team", target_id=team_id,
                               detail={"user_id": str(body.user_id), "can_write": body.can_write})
    await session.commit()
    return {"status": "ok"}


@router.post("/users/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(
    user_id: uuid.UUID,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    if user_id == actor.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用自己")
    target = await user_repo.get_by_id(session, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    await user_repo.set_active(session, user_id, False)
    await user_repo.bump_token_version(session, user_id)  # 立即切断其所有会话
    await audit_service.record(session, actor_id=actor.id, action="user.deactivate",
                               target_type="user", target_id=user_id)
    await session.commit()
    return await user_repo.get_by_id(session, user_id)


@router.post("/users/{user_id}/activate", response_model=UserOut)
async def activate_user(
    user_id: uuid.UUID,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    target = await user_repo.get_by_id(session, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    await user_repo.set_active(session, user_id, True)
    await audit_service.record(session, actor_id=actor.id, action="user.activate",
                               target_type="user", target_id=user_id)
    await session.commit()
    return await user_repo.get_by_id(session, user_id)


@router.post("/users", response_model=UserOut)
async def create_user(
    body: UserCreate,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    user = await org_service.create_user(
        session, email=body.email, password=body.password, display_name=body.display_name,
        role=body.role, department_id=body.department_id,
    )
    await audit_service.record(session, actor_id=actor.id, action="user.create",
                               target_type="user", target_id=user.id,
                               detail={"email": body.email, "role": body.role})
    await session.commit()
    return user
