from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import User
from app.repositories import user_repo
from app.schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse, UserOut
from app.services import auth_service

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    if auth_service.is_locked(body.email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录失败次数过多，请稍后再试",
        )
    user = await auth_service.authenticate(session, body.email, body.password)
    if user is None:
        auth_service.record_failure(body.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad credentials")
    auth_service.clear_failures(body.email)
    return TokenResponse(
        access_token=create_access_token(str(user.id), token_version=user.token_version)
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> None:
    """服务端登出：自增 token_version，使该用户所有存量令牌立即失效。"""
    await user_repo.bump_token_version(session, user.id)
    await session.commit()


@router.post("/auth/change-password", response_model=TokenResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """自助改密：校验旧密码 → 更新 → 自增 token_version 使其它会话失效 → 回签新令牌保当前会话。"""
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="旧密码不正确")
    await user_repo.set_password(session, user.id, hash_password(body.new_password))
    await user_repo.bump_token_version(session, user.id)
    await session.commit()
    fresh = await user_repo.get_by_id(session, user.id)
    return TokenResponse(
        access_token=create_access_token(str(user.id), token_version=fresh.token_version)
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
