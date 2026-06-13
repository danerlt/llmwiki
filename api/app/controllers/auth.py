from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.models import User
from app.repositories import user_repo
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services import auth_service

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await auth_service.authenticate(session, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad credentials")
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


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
