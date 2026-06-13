import uuid

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    kb_scope: list[uuid.UUID] | None = None


class Citation(BaseModel):
    index: int
    page_id: uuid.UUID
    title: str
    kb_id: uuid.UUID


class AnswerOut(BaseModel):
    answer: str
    citations: list[Citation]
