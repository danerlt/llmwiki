import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models import User
from app.repositories import user_repo

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


auth_service = AuthService()
