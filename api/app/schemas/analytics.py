from pydantic import BaseModel


class PageBrief(BaseModel):
    id: str
    kb_id: str
    title: str
    updated_at: str | None = None


class FeedbackCount(BaseModel):
    up: int = 0
    down: int = 0


class SearchMissItem(BaseModel):
    query: str
    count: int
    last_seen: str | None = None


class AnalyticsOut(BaseModel):
    """管理员分析看板：问答满意度 + 内容健康 + 知识空缺。"""

    feedback: FeedbackCount
    stale_days: int
    stale_pages: list[PageBrief]
    orphan_pages: list[PageBrief]
    review_due_pages: list[PageBrief]
    search_misses: list[SearchMissItem]


class ReindexResult(BaseModel):
    enabled: bool
    reindexed: int = 0
