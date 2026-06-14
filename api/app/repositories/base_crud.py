"""异步通用 CRUD 基类（对标 fastapi-project-template 的 BaseCrud）。

实体 repository 继承它即可复用"按主键查 / 列表 / 增删"，实体专属查询写在子类。
约定主键列名为 id（本项目模型统一 Uuid 主键）。get_by_id 缺失即抛 NotFoundException，
get_by_id_or_none 返回 None，统一查询的异常契约。
"""
from __future__ import annotations  # 注解惰性化：避免 list 方法名遮蔽内置 list 致注解求值失败

import uuid
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundException
from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseCrud(Generic[ModelT]):
    def __init__(self, model: type[ModelT]) -> None:
        self.model = model

    async def get_by_id_or_none(self, session: AsyncSession, id: uuid.UUID) -> ModelT | None:
        res = await session.execute(select(self.model).where(self.model.id == id))
        return res.scalar_one_or_none()

    async def get_by_id_or_raise(self, session: AsyncSession, id: uuid.UUID) -> ModelT:
        obj = await self.get_by_id_or_none(session, id)
        if obj is None:
            raise NotFoundException(f"{self.model.__name__} {id} 不存在")
        return obj

    async def list_all(self, session: AsyncSession) -> list[ModelT]:
        res = await session.execute(select(self.model))
        return list(res.scalars().all())

    async def list_by_ids(self, session: AsyncSession, ids: list[uuid.UUID]) -> list[ModelT]:
        if not ids:
            return []
        res = await session.execute(select(self.model).where(self.model.id.in_(ids)))
        return list(res.scalars().all())

    async def add(self, session: AsyncSession, obj: ModelT) -> ModelT:
        session.add(obj)
        return obj

    async def delete(self, session: AsyncSession, obj: ModelT) -> None:
        await session.delete(obj)
