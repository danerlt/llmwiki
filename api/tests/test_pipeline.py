import json

from app.ingest.pipeline import PageDraft, analyze, extract_wikilinks, generate_pages
from tests.fakes import FakeLLM


async def test_analyze_parses_json_with_fences():
    analysis = {"entities": ["A"], "concepts": ["B"], "key_claims": [],
                "links_to_existing": [], "contradictions": []}
    llm = FakeLLM(["```json\n" + json.dumps(analysis) + "\n```"])
    out = await analyze(llm, "some text")
    assert out["entities"] == ["A"] and out["concepts"] == ["B"]


async def test_analyze_falls_back_on_bad_json():
    llm = FakeLLM(["not json at all"])
    out = await analyze(llm, "text")
    assert out == {"entities": [], "concepts": [], "key_claims": [],
                   "links_to_existing": [], "contradictions": []}


async def test_generate_pages_parses_and_constrains_page_type():
    pages = [
        {"title": "实体A", "slug": "实体A", "page_type": "entity", "content_md": "见 [[概念B]]"},
        {"title": "怪类型", "slug": "x", "page_type": "bogus", "content_md": "y"},
    ]
    llm = FakeLLM(["```json\n" + json.dumps(pages) + "\n```"])
    drafts = await generate_pages(llm, {"entities": ["A"]}, index_md="")
    assert all(isinstance(d, PageDraft) for d in drafts)
    types = {d.page_type for d in drafts}
    assert "entity" in types
    assert "bogus" not in types and "concept" in types  # 非法类型降级为 concept


def test_extract_wikilinks():
    # slug 归一化（ASCII 小写），故 概念B → 概念b、实体A → 实体a
    assert extract_wikilinks("见 [[概念B]] 与 [[实体A]]，再引 [[概念B]]") == ["概念b", "实体a"]
