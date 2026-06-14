from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories import comment_repo, user_repo, wiki_repo
from app.schemas.activity import ActivityItem
from app.services.permission_service import permission_service


class ActivityService:
    """动态流：可见知识库内的页面更新 + 评论，按时间倒序合并。"""

    async def list_activity(self, session: AsyncSession, user: User) -> list[ActivityItem]:
        kb_ids = list(await permission_service.accessible_kb_ids(session, user))
        items: list[ActivityItem] = []
        for p in await wiki_repo.recent(session, kb_ids, limit=15):
            items.append(
                ActivityItem(
                    type="page.updated",
                    page_id=str(p.id),
                    title=p.title,
                    at=p.updated_at.isoformat() if p.updated_at else None,
                    text=f"《{p.title}》有更新",
                )
            )
        for c, p in await comment_repo.recent_in_kbs(session, kb_ids, limit=15):
            author = await user_repo.get_by_id(session, c.author_id)
            items.append(
                ActivityItem(
                    type="page.commented",
                    page_id=str(p.id),
                    title=p.title,
                    at=c.created_at.isoformat() if c.created_at else None,
                    text=f"{author.display_name if author else '某人'} 评论了《{p.title}》",
                )
            )
        items.sort(key=lambda x: x.at or "", reverse=True)
        return items[:20]


activity_service = ActivityService()
