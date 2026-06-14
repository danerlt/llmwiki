import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Favorite, WikiPage
from app.repositories.base_crud import BaseCrud


class FavoriteRepo(BaseCrud[Favorite]):
    """收藏仓储：通用增删查继承自 BaseCrud，下为实体专属查询。"""

    def __init__(self) -> None:
        super().__init__(Favorite)

    async def add(self, session: AsyncSession, *, user_id: uuid.UUID, page_id: uuid.UUID) -> None:
        if not await self.exists(session, user_id=user_id, page_id=page_id):
            session.add(Favorite(user_id=user_id, page_id=page_id))

    async def remove(self, session: AsyncSession, *, user_id: uuid.UUID, page_id: uuid.UUID) -> None:
        await session.execute(
            delete(Favorite).where(Favorite.user_id == user_id, Favorite.page_id == page_id)
        )

    async def exists(self, session: AsyncSession, *, user_id: uuid.UUID, page_id: uuid.UUID) -> bool:
        res = await session.execute(
            select(Favorite.id).where(Favorite.user_id == user_id, Favorite.page_id == page_id)
        )
        return res.first() is not None

    async def list_pages(self, session: AsyncSession, user_id: uuid.UUID) -> list[WikiPage]:
        res = await session.execute(
            select(WikiPage)
            .join(Favorite, Favorite.page_id == WikiPage.id)
            .where(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
        )
        return list(res.scalars().all())


favorite_repo = FavoriteRepo()
