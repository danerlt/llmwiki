import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnswerFeedback


async def create(
    session: AsyncSession, *, user_id: uuid.UUID, question: str, answer: str, vote: str
) -> AnswerFeedback:
    fb = AnswerFeedback(user_id=user_id, question=question, answer=answer, vote=vote)
    session.add(fb)
    return fb


async def counts(session: AsyncSession) -> dict[str, int]:
    """按 vote 聚合（up/down 计数），供质量看板。"""
    res = await session.execute(
        select(AnswerFeedback.vote, func.count()).group_by(AnswerFeedback.vote)
    )
    return {row[0]: int(row[1]) for row in res.all()}
