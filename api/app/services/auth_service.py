import time
import uuid

from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ParamsException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.repositories import api_key_repo, comment_repo, favorite_repo, user_repo
from app.schemas.auth import TokenResponse, UserOut

_MAX_FAILS = 5
_WINDOW = 900  # 15 分钟


class AuthService:
    def __init__(self) -> None:
        # 进程内登录失败计数：email -> 最近失败时间戳列表。暴力破解防护（多实例需换 Redis）。
        self._fails: dict[str, list[float]] = {}

    def is_locked(self, email: str) -> bool:
        ts = [t for t in self._fails.get(email, []) if time.time() - t < _WINDOW]
        self._fails[email] = ts
        return len(ts) >= _MAX_FAILS

    def record_failure(self, email: str) -> None:
        self._fails.setdefault(email, []).append(time.time())

    def clear_failures(self, email: str) -> None:
        self._fails.pop(email, None)

    def reset_lockout(self) -> None:
        self._fails.clear()

    async def authenticate(self, session: AsyncSession, email: str, password: str) -> User | None:
        user = await user_repo.get_by_email(session, email)
        if user is None or not verify_password(password, user.password_hash):
            return None
        return user

    async def login(self, session: AsyncSession, email: str, password: str) -> TokenResponse:
        """校验凭据并签发访问/刷新令牌；失败时记录失败计数并抛 401。"""
        user = await self.authenticate(session, email, password)
        if user is None:
            self.record_failure(email)
            raise UnauthorizedException("bad credentials")
        self.clear_failures(email)
        return TokenResponse(
            access_token=create_access_token(str(user.id), token_version=user.token_version),
            refresh_token=create_refresh_token(str(user.id), token_version=user.token_version),
        )

    async def refresh(self, session: AsyncSession, refresh_token: str) -> TokenResponse:
        """用刷新令牌换取新的访问令牌（校验 type/exp/token_version 与账号有效）。"""
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise UnauthorizedException("invalid refresh token")
        if payload.get("type") != "refresh":
            raise UnauthorizedException("not a refresh token")
        user = await user_repo.get_by_id(session, uuid.UUID(payload["sub"]))
        if user is None or not user.is_active or payload.get("tv", 0) != user.token_version:
            raise UnauthorizedException("refresh token revoked")
        return TokenResponse(
            access_token=create_access_token(str(user.id), token_version=user.token_version),
            refresh_token=create_refresh_token(str(user.id), token_version=user.token_version),
        )

    async def logout(self, session: AsyncSession, user: User) -> None:
        """服务端登出：自增 token_version，使该用户所有存量令牌立即失效。"""
        await user_repo.bump_token_version(session, user.id)
        await session.commit()

    async def change_password(
        self, session: AsyncSession, user: User, old_password: str, new_password: str
    ) -> TokenResponse:
        """自助改密：校验旧密码 → 更新 → 自增 token_version 使其它会话失效 → 回签新令牌保当前会话。"""
        if not verify_password(old_password, user.password_hash):
            raise ParamsException("旧密码不正确")
        await user_repo.set_password(session, user.id, hash_password(new_password))
        await user_repo.bump_token_version(session, user.id)
        await session.commit()
        fresh = await user_repo.get_by_id(session, user.id)
        return TokenResponse(
            access_token=create_access_token(str(user.id), token_version=fresh.token_version)
        )

    def get_me(self, user: User) -> UserOut:
        return UserOut.model_validate(user)

    async def export_my_data(self, session: AsyncSession, user: User) -> dict:
        """GDPR 数据主体请求（DSAR）：收集当前用户的个人数据。"""
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


auth_service = AuthService()
