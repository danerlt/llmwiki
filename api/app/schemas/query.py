import uuid

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    kb_scope: list[uuid.UUID] | None = None


class Citation(BaseModel):
    page_id: uuid.UUID
    title: str
    kb_id: uuid.UUID


class AnswerOut(BaseModel):
    answer: str
    citations: list[Citation]
