import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services import retrieval_service

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_CITE_RE = re.compile(r"\[(\d+)\]")

QUERY_SYSTEM = (
    "你是企业知识库问答助手。只依据给定编号资料作答，使用清晰的 Markdown（要点用无序列表、"
    "关键术语适度加粗）。每条事实在句末用 [n] 标注其来源编号；资料不足就直说不知道，不要编造。"
)
_PAGE_CHAR_BUDGET = 2000


async def answer(
    session: AsyncSession, user: User, question: str, kb_scope=None, *, llm
) -> dict:
    pages = [
        p
        for p in await retrieval_service.retrieve(session, user, question, kb_scope)
        if p.page_type != "index"  # 目录页只是导航地图，不作为引用来源
    ]
    if not pages:
        return {"answer": "（在你可见的知识库中没有找到相关内容，无法回答）", "citations": []}

    parts: list[str] = []
    citations: list[dict] = []
    for i, p in enumerate(pages, 1):
        body = (p.content_md or "")[:_PAGE_CHAR_BUDGET]
        parts.append(f"[{i}] {p.title}\n{body}")
        citations.append({"index": i, "page_id": p.id, "title": p.title, "kb_id": p.kb_id})

    user_prompt = f"问题：{question}\n\n资料：\n" + "\n\n".join(parts)
    try:
        answer_text = await llm.complete(QUERY_SYSTEM, user_prompt)
    except Exception:  # noqa: BLE001 — LLM 不可用时降级返回，不裸 500
        return {"answer": "（问答服务暂不可用，请稍后重试）", "citations": citations}

    answer_text = _WIKILINK.sub(r"\1", answer_text)
    # 只保留答案里真正用 [n] 引用到的来源；模型若未标注则回退展示全部
    used = {int(m.group(1)) for m in _CITE_RE.finditer(answer_text)}
    cited = [c for c in citations if c["index"] in used]
    return {"answer": answer_text, "citations": cited or citations}
