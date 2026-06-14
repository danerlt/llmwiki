import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ForbiddenException, NotFoundException
from app.models import User, WikiPage
from app.repositories import favorite_repo, wiki_repo
from app.schemas.wiki import PageOut
from app.services.permission_service import permission_service


class FavoriteService:
    """页面收藏。"""

    async def _readable_page(
        self, session: AsyncSession, page_id: uuid.UUID, user: User
    ) -> WikiPage:
        page = await wiki_repo.get_by_id(session, page_id)
        if page is None:
            raise NotFoundException("page not found")
        if page.kb_id not in await permission_service.accessible_kb_ids(session, user):
            raise ForbiddenException("no access")
        return page

    async def list_favorites(self, session: AsyncSession, user: User) -> list[PageOut]:
        accessible = await permission_service.accessible_kb_ids(session, user)
        # 仅返回当前仍可见的收藏页（作用域可能已变化）
        pages = await favorite_repo.list_pages(session, user.id)
        return [PageOut.model_validate(p) for p in pages if p.kb_id in accessible]

    async def add_favorite(self, session: AsyncSession, user: User, page_id: uuid.UUID) -> None:
        await self._readable_page(session, page_id, user)
        await favorite_repo.add(session, user_id=user.id, page_id=page_id)
        await session.commit()

    async def remove_favorite(self, session: AsyncSession, user: User, page_id: uuid.UUID) -> None:
        await favorite_repo.remove(session, user_id=user.id, page_id=page_id)
        await session.commit()


favorite_service = FavoriteService()
