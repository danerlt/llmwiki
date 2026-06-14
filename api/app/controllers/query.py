from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.integrations.llm import LLMClient
from app.models import User
from app.schemas.query import AnswerOut, FeedbackRequest, FeedbackResult, QueryRequest
from app.services import query_service

router = APIRouter(tags=["query"])


def get_llm() -> LLMClient:
    return LLMClient(
        base_url=settings.llm_base_url, api_key=settings.llm_api_key, model=settings.llm_model
    )


@router.post("/query", response_model=Response[AnswerOut])
@api_response
async def query(
    body: QueryRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    history = [t.model_dump() for t in body.history] if body.history else None
    return await query_service.answer(
        session, user, body.question, kb_scope=body.kb_scope, llm=llm, history=history
    )


@router.post(
    "/query/feedback",
    status_code=status.HTTP_201_CREATED,
    response_model=Response[FeedbackResult],
)
@api_response
async def query_feedback(
    body: FeedbackRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """记录问答答案反馈（赞/踩），用于度量与迭代 AI 质量。"""
    return await query_service.record_feedback(session, user, body)


@router.post("/query/stream")
async def query_stream(
    body: QueryRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    """SSE 流式问答：回答边生成边推送，结束推送引用来源。"""
    history = [t.model_dump() for t in body.history] if body.history else None
    gen = query_service.answer_stream(
        session, user, body.question, kb_scope=body.kb_scope, llm=llm, history=history
    )
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
