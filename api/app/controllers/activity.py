from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import comment_repo, user_repo, wiki_repo
from app.services import permission_service

router = APIRouter(tags=["activity"])


@router.get("/activity")
async def activity(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    """可见知识库内的最近动态：页面更新 + 评论，按时间倒序合并。"""
    kb_ids = list(await permission_service.accessible_kb_ids(session, user))
    items: list[dict] = []
    for p in await wiki_repo.recent(session, kb_ids, limit=15):
        items.append({
            "type": "page.updated",
            "page_id": str(p.id),
            "title": p.title,
            "at": p.updated_at.isoformat() if p.updated_at else None,
            "text": f"《{p.title}》有更新",
        })
    for c, p in await comment_repo.recent_in_kbs(session, kb_ids, limit=15):
        author = await user_repo.get_by_id(session, c.author_id)
        items.append({
            "type": "page.commented",
            "page_id": str(p.id),
            "title": p.title,
            "at": c.created_at.isoformat() if c.created_at else None,
            "text": f"{author.display_name if author else '某人'} 评论了《{p.title}》",
        })
    items.sort(key=lambda x: x["at"] or "", reverse=True)
    return items[:20]
