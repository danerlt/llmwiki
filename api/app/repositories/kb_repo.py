import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase
from app.repositories.base_crud import BaseCrud


class KbRepo(BaseCrud[KnowledgeBase]):
    """知识库仓储：通用增删查继承自 BaseCrud，下为实体专属查询。"""

    def __init__(self) -> None:
        super().__init__(KnowledgeBase)

    async def create(
        self, session: AsyncSession, *, scope_type: str, scope_ref_id: uuid.UUID | None, name: str
    ) -> KnowledgeBase:
        kb = KnowledgeBase(scope_type=scope_type, scope_ref_id=scope_ref_id, name=name)
        session.add(kb)
        return kb

    async def get_by_id(self, session: AsyncSession, kb_id: uuid.UUID) -> KnowledgeBase | None:
        # 保留既有"缺失返回 None"契约（等价 BaseCrud.get_by_id_or_none）
        return await self.get_by_id_or_none(session, kb_id)

    async def list_by_scope(
        self, session: AsyncSession, scope_type: str, scope_ref_id: uuid.UUID | None
    ) -> list[KnowledgeBase]:
        stmt = select(KnowledgeBase).where(KnowledgeBase.scope_type == scope_type)
        stmt = stmt.where(
            KnowledgeBase.scope_ref_id == scope_ref_id
            if scope_ref_id is not None
            else KnowledgeBase.scope_ref_id.is_(None)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    # list_by_ids 继承自 BaseCrud（与原实现一致）


kb_repo = KbRepo()
