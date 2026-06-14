import json
import re
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services import retrieval_service

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_CITE_RE = re.compile(r"\[(\d+)\]")

QUERY_SYSTEM = (
    "你是企业知识库问答助手。只依据给定编号资料作答，使用清晰的 Markdown（要点用无序列表、"
    "关键术语适度加粗）。每条事实在句末用 [n] 标注其来源编号；方括号【只】用于来源编号，"
    "不要给术语或名词套方括号。资料不足就直说不知道，不要编造。"
)
_PAGE_CHAR_BUDGET = 2000


_NO_CONTEXT = "（在你可见的知识库中没有找到相关内容，无法回答）"


async def _prepare(session: AsyncSession, user: User, question: str, kb_scope):
    """权限感知检索 → 构造编号资料 prompt 与候选引用。无可用内容时返回 None。"""
    pages = [
        p
        for p in await retrieval_service.retrieve(session, user, question, kb_scope)
        if p.page_type != "index"  # 目录页只是导航地图，不作为引用来源
    ]
    if not pages:
        return None
    parts: list[str] = []
    citations: list[dict] = []
    for i, p in enumerate(pages, 1):
        body = (p.content_md or "")[:_PAGE_CHAR_BUDGET]
        parts.append(f"[{i}] {p.title}\n{body}")
        citations.append({"index": i, "page_id": p.id, "title": p.title, "kb_id": p.kb_id})
    user_prompt = f"问题：{question}\n\n资料：\n" + "\n\n".join(parts)
    return citations, user_prompt


def _filter_citations(answer_text: str, citations: list[dict]) -> list[dict]:
    """只保留答案里真正用 [n] 引用到的来源；模型未标注则回退展示全部。"""
    used = {int(m.group(1)) for m in _CITE_RE.finditer(answer_text)}
    cited = [c for c in citations if c["index"] in used]
    return cited or citations


async def answer(
    session: AsyncSession, user: User, question: str, kb_scope=None, *, llm, history=None
) -> dict:
    prep = await _prepare(session, user, question, kb_scope)
    if prep is None:
        return {"answer": _NO_CONTEXT, "citations": []}
    citations, user_prompt = prep
    try:
        answer_text = await llm.complete(QUERY_SYSTEM, user_prompt, history=history)
    except Exception:  # noqa: BLE001 — LLM 不可用时降级返回，不裸 500
        return {"answer": "（问答服务暂不可用，请稍后重试）", "citations": citations}
    answer_text = _WIKILINK.sub(r"\1", answer_text)
    return {"answer": answer_text, "citations": _filter_citations(answer_text, citations)}


def _sse(obj: dict) -> str:
    return "data: " + json.dumps(obj, ensure_ascii=False, default=str) + "\n\n"


async def answer_stream(
    session: AsyncSession, user: User, question: str, kb_scope=None, *, llm, history=None
) -> AsyncIterator[str]:
    """SSE 流式问答：先逐 token 推送 {delta}，结束时推送 {done, citations}。"""
    prep = await _prepare(session, user, question, kb_scope)
    if prep is None:
        yield _sse({"delta": _NO_CONTEXT})
        yield _sse({"done": True, "citations": []})
        return
    citations, user_prompt = prep
    acc: list[str] = []
    try:
        async for delta in llm.stream(QUERY_SYSTEM, user_prompt, history=history):
            acc.append(delta)
            yield _sse({"delta": delta})
    except Exception:  # noqa: BLE001 — 流中断则降级收尾
        yield _sse({"delta": "\n\n（问答服务中断，请稍后重试）", "done": True, "citations": []})
        return
    answer_text = _WIKILINK.sub(r"\1", "".join(acc))
    yield _sse({"done": True, "citations": _filter_citations(answer_text, citations)})
