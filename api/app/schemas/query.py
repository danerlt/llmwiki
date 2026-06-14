import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str = Field(max_length=8000)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    kb_scope: list[uuid.UUID] | None = None
    history: list[ChatTurn] | None = Field(default=None, max_length=20)  # 多轮上下文


class FeedbackRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(min_length=1, max_length=20000)
    vote: Literal["up", "down"]


class Citation(BaseModel):
    index: int
    page_id: uuid.UUID
    title: str
    kb_id: uuid.UUID


class AnswerOut(BaseModel):
    answer: str
    citations: list[Citation]


class FeedbackResult(BaseModel):
    ok: bool = True
