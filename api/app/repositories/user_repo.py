import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories.base_crud import BaseCrud


class UserRepo(BaseCrud[User]):
    """用户仓储：通用增删查继承自 BaseCrud，下为实体专属查询。"""

    def __init__(self) -> None:
        super().__init__(User)

    async def create(
        self,
        session: AsyncSession,
        *,
        email: str,
        password_hash: str,
        display_name: str,
        role: str = "user",
        department_id: uuid.UUID | None = None,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            role=role,
            department_id=department_id,
        )
        session.add(user)
        return user

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        res = await session.execute(select(User).where(User.email == email))
        return res.scalar_one_or_none()

    async def get_by_id(self, session: AsyncSession, user_id: uuid.UUID) -> User | None:
        # 保留既有"缺失返回 None"契约（等价 BaseCrud.get_by_id_or_none）
        return await self.get_by_id_or_none(session, user_id)

    async def set_active(self, session: AsyncSession, user_id: uuid.UUID, active: bool) -> None:
        await session.execute(update(User).where(User.id == user_id).values(is_active=active))

    async def set_password(self, session: AsyncSession, user_id: uuid.UUID, password_hash: str) -> None:
        await session.execute(
            update(User).where(User.id == user_id).values(password_hash=password_hash)
        )

    async def bump_token_version(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        """自增会话版本：使该用户所有存量 JWT 失效（登出/封禁/改密）。"""
        await session.execute(
            update(User).where(User.id == user_id).values(token_version=User.token_version + 1)
        )

    # list_all 继承自 BaseCrud（与原实现一致）


user_repo = UserRepo()
