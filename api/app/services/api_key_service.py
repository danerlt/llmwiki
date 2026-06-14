import hashlib
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey, User
from app.repositories import api_key_repo, user_repo


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def issue(session: AsyncSession, *, user_id, name: str) -> tuple[ApiKey, str]:
    """生成新 Key：返回 (记录, 明文)。明文形如 lk_<prefix>_<secret>，仅此一次可见。"""
    prefix = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    raw = f"lk_{prefix}_{secret}"
    rec = await api_key_repo.create(
        session, user_id=user_id, name=name, prefix=prefix, key_hash=_hash(raw)
    )
    return rec, raw


async def resolve(session: AsyncSession, raw: str) -> User | None:
    """用明文 Key 解析出 owner（须有效且账号 active）。"""
    rec = await api_key_repo.get_by_hash(session, _hash(raw))
    if rec is None:
        return None
    user = await user_repo.get_by_id(session, rec.user_id)
    if user is None or not user.is_active:
        return None
    return user
