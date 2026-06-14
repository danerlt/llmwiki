import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PromotionRequest
from app.repositories.base_crud import BaseCrud


class PromotionRepo(BaseCrud[PromotionRequest]):
    """晋升请求仓储：通用增删查继承自 BaseCrud，下为实体专属查询。"""

    def __init__(self) -> None:
        super().__init__(PromotionRequest)

    async def create(
        self,
        session: AsyncSession,
        *,
        page_id: uuid.UUID,
        to_kb_id: uuid.UUID,
        requested_by: uuid.UUID,
        note: str | None = None,
    ) -> PromotionRequest:
        pr = PromotionRequest(
            page_id=page_id, to_kb_id=to_kb_id, requested_by=requested_by, note=note
        )
        session.add(pr)
        return pr

    async def get_by_id(self, session: AsyncSession, pr_id: uuid.UUID) -> PromotionRequest | None:
        # 保留既有"缺失返回 None"契约（等价 BaseCrud.get_by_id_or_none）
        return await self.get_by_id_or_none(session, pr_id)

    async def list_pending(self, session: AsyncSession) -> list[PromotionRequest]:
        res = await session.execute(
            select(PromotionRequest).where(PromotionRequest.status == "pending")
        )
        return list(res.scalars().all())


promotion_repo = PromotionRepo()
