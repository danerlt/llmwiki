"""阶段4 异步 BaseCrud 的通用 CRUD 行为。"""
import uuid

import pytest

from app.common.exceptions import NotFoundException
from app.models import KnowledgeBase
from app.repositories.base_crud import BaseCrud

kb_crud: BaseCrud[KnowledgeBase] = BaseCrud(KnowledgeBase)


async def test_get_by_id_or_none_returns_none_when_missing(session):
    assert await kb_crud.get_by_id_or_none(session, uuid.uuid4()) is None


async def test_get_by_id_or_raise_raises_not_found_when_missing(session):
    with pytest.raises(NotFoundException):
        await kb_crud.get_by_id_or_raise(session, uuid.uuid4())


async def test_add_then_get_by_id_or_raise(session):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name="公司")
    await kb_crud.add(session, kb)
    await session.flush()
    got = await kb_crud.get_by_id_or_raise(session, kb.id)
    assert got.id == kb.id and got.name == "公司"


async def test_list_by_ids(session):
    a = KnowledgeBase(scope_type="company", scope_ref_id=None, name="A")
    b = KnowledgeBase(scope_type="company", scope_ref_id=None, name="B")
    await kb_crud.add(session, a)
    await kb_crud.add(session, b)
    await session.flush()
    got = await kb_crud.list_by_ids(session, [a.id, b.id])
    assert {k.name for k in got} == {"A", "B"}
    assert await kb_crud.list_by_ids(session, []) == []


async def test_delete_removes_row(session):
    kb = KnowledgeBase(scope_type="company", scope_ref_id=None, name="待删")
    await kb_crud.add(session, kb)
    await session.flush()
    await kb_crud.delete(session, kb)
    await session.flush()
    assert await kb_crud.get_by_id_or_none(session, kb.id) is None
