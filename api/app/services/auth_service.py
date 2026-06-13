from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models import User
from app.repositories import user_repo


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    user = await user_repo.get_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user
