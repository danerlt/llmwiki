from pydantic import BaseModel


class ActivityItem(BaseModel):
    """动态流条目：页面更新或评论。"""

    type: str
    page_id: str
    title: str
    at: str | None = None
    text: str
