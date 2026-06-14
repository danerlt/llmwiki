from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
import uuid

from jose import JWTError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models import User
from app.repositories import api_key_repo, comment_repo, favorite_repo, user_repo
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
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
        access_token=create_access_token(str(user.id), token_version=user.token_version),
        refresh_token=create_refresh_token(str(user.id), token_version=user.token_version),
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    """用刷新令牌换取新的访问令牌（校验 type/exp/token_version 与账号有效）。"""
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not a refresh token")
    user = await user_repo.get_by_id(session, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active or payload.get("tv", 0) != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh token revoked")
    return TokenResponse(
        access_token=create_access_token(str(user.id), token_version=user.token_version),
        refresh_token=create_refresh_token(str(user.id), token_version=user.token_version),
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


@router.get("/me/export")
async def export_my_data(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """GDPR 数据主体请求（DSAR）：导出当前用户的个人数据。"""
    comments = await comment_repo.list_by_author(session, user.id)
    favorites = await favorite_repo.list_pages(session, user.id)
    keys = await api_key_repo.list_by_user(session, user.id)
    return {
        "profile": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
        },
        "comments": [
            {"page_id": str(c.page_id), "body": c.body, "created_at": c.created_at.isoformat()}
            for c in comments
        ],
        "favorites": [{"page_id": str(p.id), "title": p.title} for p in favorites],
        "api_keys": [{"name": k.name, "prefix": k.prefix, "revoked": k.revoked} for k in keys],
    }
