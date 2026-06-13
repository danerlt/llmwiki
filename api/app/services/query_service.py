from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services import retrieval_service

QUERY_SYSTEM = (
    "你是企业知识库问答助手。只依据给定编号资料回答，"
    "在句末用 [n] 标注引用；资料不足就说不知道。"
)
_PAGE_CHAR_BUDGET = 2000  # 每页正文截断上限


async def answer(
    session: AsyncSession, user: User, question: str,
    kb_scope=None, *, llm,
) -> dict:
    pages = await retrieval_service.retrieve(session, user, question, kb_scope)
    if not pages:
        return {"answer": "（无可用知识，无法回答）", "citations": []}

    parts: list[str] = []
    citations: list[dict] = []
    for i, p in enumerate(pages, 1):
        body = (p.content_md or "")[:_PAGE_CHAR_BUDGET]
        parts.append(f"[{i}] {p.title}\n{body}")
        citations.append({"page_id": p.id, "title": p.title, "kb_id": p.kb_id})

    user_prompt = f"问题：{question}\n\n资料：\n" + "\n\n".join(parts)
    answer_text = await llm.complete(QUERY_SYSTEM, user_prompt)
    return {"answer": answer_text, "citations": citations}
