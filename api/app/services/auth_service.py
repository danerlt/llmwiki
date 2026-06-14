import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models import User
from app.repositories import user_repo

# 进程内登录失败计数：email -> 最近失败时间戳列表。暴力破解防护（多实例需换 Redis）。
_fails: dict[str, list[float]] = {}
_MAX_FAILS = 5
_WINDOW = 900  # 15 分钟


def is_locked(email: str) -> bool:
    ts = [t for t in _fails.get(email, []) if time.time() - t < _WINDOW]
    _fails[email] = ts
    return len(ts) >= _MAX_FAILS


def record_failure(email: str) -> None:
    _fails.setdefault(email, []).append(time.time())


def clear_failures(email: str) -> None:
    _fails.pop(email, None)


def reset_lockout() -> None:
    _fails.clear()


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    user = await user_repo.get_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user
