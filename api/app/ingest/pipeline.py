import json
import re
from dataclasses import dataclass, field

from app.ingest.parser import slugify
from app.models.wiki_page import PAGE_TYPES

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_ANALYZE_KEYS = ("entities", "concepts", "key_claims", "links_to_existing", "contradictions")

ANALYZE_SYSTEM = (
    "你是知识抽取器。阅读文本，输出 JSON，键为 "
    "entities/concepts/key_claims/links_to_existing/contradictions，值均为字符串数组。只输出 JSON。"
)
GENERATE_SYSTEM = (
    "你是企业 wiki 编辑。依据分析结果与现有目录，产出 wiki 页 JSON 数组；"
    "每项含 title/slug/page_type/content_md，page_type ∈ "
    "[source_summary,entity,concept,overview]。\n"
    "content_md 必须内容充实、结构清晰（约 150–400 字）：用 2–4 个 ## 小标题分节，"
    "配合无序列表/要点，必要时给简短代码或表格；在正文中用 [[wikilink]] 交叉引用相关条目。"
    "不要写空洞的一句话页。只输出 JSON 数组。"
)


@dataclass
class PageDraft:
    title: str
    slug: str
    page_type: str
    content_md: str
    frontmatter: dict = field(default_factory=dict)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip()


async def analyze(llm, text: str) -> dict:
    raw = await llm.complete(ANALYZE_SYSTEM, text)
    try:
        data = json.loads(_strip_fences(raw))
    except (json.JSONDecodeError, TypeError):
        data = {}
    return {k: (data.get(k) if isinstance(data.get(k), list) else []) for k in _ANALYZE_KEYS}


async def generate_pages(llm, analysis: dict, index_md: str) -> list[PageDraft]:
    user = f"分析结果:\n{json.dumps(analysis, ensure_ascii=False)}\n\n现有目录:\n{index_md}"
    raw = await llm.complete(GENERATE_SYSTEM, user)
    try:
        items = json.loads(_strip_fences(raw))
    except (json.JSONDecodeError, TypeError):
        items = []
    if not isinstance(items, list):
        items = []
    drafts: list[PageDraft] = []
    for it in items:
        if not isinstance(it, dict) or not it.get("title"):
            continue
        ptype = it.get("page_type")
        if ptype not in PAGE_TYPES or ptype == "index":
            ptype = "concept"  # 非法或保留类型降级
        title = str(it["title"])
        drafts.append(
            PageDraft(
                title=title,
                slug=slugify(str(it.get("slug") or title)),
                page_type=ptype,
                content_md=str(it.get("content_md", "")),
            )
        )
    return drafts


def extract_wikilinks(content_md: str) -> list[str]:
    """提取 [[目标]] 的 slug 列表（去重保序）。"""
    slugs = [slugify(m.group(1)) for m in _WIKILINK.finditer(content_md)]
    return list(dict.fromkeys(slugs))
