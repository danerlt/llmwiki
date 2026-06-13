import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def create(
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


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    res = await session.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    res = await session.execute(select(User).where(User.id == user_id))
    return res.scalar_one_or_none()


async def list_all(session: AsyncSession) -> list[User]:
    res = await session.execute(select(User))
    return list(res.scalars().all())


async def bump_token_version(session: AsyncSession, user_id: uuid.UUID) -> None:
    """自增会话版本：使该用户所有存量 JWT 失效（登出/封禁/改密）。"""
    await session.execute(
        update(User).where(User.id == user_id).values(token_version=User.token_version + 1)
    )
