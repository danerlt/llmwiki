import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Webhook
from app.repositories.base_crud import BaseCrud


class WebhookRepo(BaseCrud[Webhook]):
    """Webhook 仓储：通用增删查继承自 BaseCrud，下为实体专属查询。"""

    def __init__(self) -> None:
        super().__init__(Webhook)

    async def create(
        self, session: AsyncSession, *, created_by: uuid.UUID, url: str, secret: str
    ) -> Webhook:
        w = Webhook(created_by=created_by, url=url, secret=secret)
        session.add(w)
        return w

    async def list_all(self, session: AsyncSession) -> list[Webhook]:
        res = await session.execute(select(Webhook).order_by(Webhook.created_at.desc()))
        return list(res.scalars().all())

    async def list_active(self, session: AsyncSession) -> list[Webhook]:
        res = await session.execute(select(Webhook).where(Webhook.active.is_(True)))
        return list(res.scalars().all())

    async def get_by_id(self, session: AsyncSession, webhook_id: uuid.UUID) -> Webhook | None:
        # 保留既有“缺失返回 None”契约（等价 BaseCrud.get_by_id_or_none）
        return await self.get_by_id_or_none(session, webhook_id)


webhook_repo = WebhookRepo()
