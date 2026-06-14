import hashlib
import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundException
from app.models import ApiKey, User
from app.repositories import api_key_repo, user_repo
from app.schemas.api_key import ApiKeyCreated, ApiKeyOut
from app.services.audit_service import audit_service


class ApiKeyService:
    def _hash(self, raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    async def issue(self, session: AsyncSession, *, user_id, name: str) -> tuple[ApiKey, str]:
        """生成新 Key：返回 (记录, 明文)。明文形如 lk_<prefix>_<secret>，仅此一次可见。"""
        prefix = secrets.token_hex(4)
        secret = secrets.token_urlsafe(32)
        raw = f"lk_{prefix}_{secret}"
        rec = await api_key_repo.create(
            session, user_id=user_id, name=name, prefix=prefix, key_hash=self._hash(raw)
        )
        return rec, raw

    async def resolve(self, session: AsyncSession, raw: str) -> User | None:
        """用明文 Key 解析出 owner（须有效且账号 active）。"""
        rec = await api_key_repo.get_by_hash(session, self._hash(raw))
        if rec is None:
            return None
        user = await user_repo.get_by_id(session, rec.user_id)
        if user is None or not user.is_active:
            return None
        return user

    async def list_my_keys(self, session: AsyncSession, user: User) -> list[ApiKeyOut]:
        """列出当前用户的全部 Key。"""
        rows = await api_key_repo.list_by_user(session, user.id)
        return [ApiKeyOut.model_validate(r) for r in rows]

    async def create_key(self, session: AsyncSession, user: User, name: str) -> ApiKeyCreated:
        """创建 Key 并记审计，返回含明文的创建结果（明文仅此一次可见）。"""
        rec, raw = await self.issue(session, user_id=user.id, name=name)
        await audit_service.record(
            session,
            actor_id=user.id,
            action="apikey.create",
            target_type="api_key",
            target_id=rec.id,
            detail={"name": name},
        )
        await session.commit()
        return ApiKeyCreated(
            id=rec.id,
            name=rec.name,
            prefix=rec.prefix,
            revoked=rec.revoked,
            created_at=rec.created_at,
            last_used_at=rec.last_used_at,
            key=raw,
        )

    async def revoke_key(self, session: AsyncSession, user: User, key_id: uuid.UUID) -> None:
        """撤销当前用户的 Key 并记审计。Key 不存在或非本人所有时抛 NotFoundException。"""
        rec = await api_key_repo.get_owned(session, key_id, user.id)
        if rec is None:
            raise NotFoundException("key not found")
        rec.revoked = True
        await audit_service.record(
            session,
            actor_id=user.id,
            action="apikey.revoke",
            target_type="api_key",
            target_id=key_id,
        )
        await session.commit()


api_key_service = ApiKeyService()
