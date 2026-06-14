from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from app.services import auth_service

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=Response[TokenResponse])
@api_response
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    if auth_service.is_locked(body.email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录失败次数过多，请稍后再试",
        )
    return await auth_service.login(session, body.email, body.password)


@router.post("/auth/refresh", response_model=Response[TokenResponse])
@api_response
async def refresh(body: RefreshRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    return await auth_service.refresh(session, body.refresh_token)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
@api_response
async def logout(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> None:
    await auth_service.logout(session, user)


@router.post("/auth/change-password", response_model=Response[TokenResponse])
@api_response
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await auth_service.change_password(
        session, user, body.old_password, body.new_password
    )


@router.get("/me", response_model=Response[UserOut])
@api_response
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return auth_service.get_me(user)


@router.get("/me/export")
async def export_my_data(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """GDPR 数据主体请求（DSAR）：导出当前用户的个人数据。"""
    return await auth_service.export_my_data(session, user)
