import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import comment_repo, user_repo, wiki_repo
from app.schemas.comment import CommentCreate, CommentOut
from app.services import audit_service, notification_service, permission_service

router = APIRouter(tags=["comments"])


async def _readable_page(session: AsyncSession, page_id: uuid.UUID, user: User):
    page = await wiki_repo.get_by_id(session, page_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page not found")
    accessible = await permission_service.accessible_kb_ids(session, user)
    if page.kb_id not in accessible:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no access")
    return page


def _out(c, name: str) -> CommentOut:
    return CommentOut(
        id=c.id, page_id=c.page_id, author_id=c.author_id,
        author_name=name, body=c.body, created_at=c.created_at,
    )


@router.get("/pages/{page_id}/comments", response_model=list[CommentOut])
async def list_comments(
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await _readable_page(session, page_id, user)
    out: list[CommentOut] = []
    for c in await comment_repo.list_by_page(session, page_id):
        author = await user_repo.get_by_id(session, c.author_id)
        out.append(_out(c, author.display_name if author else "(未知)"))
    return out


@router.post("/pages/{page_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def add_comment(
    page_id: uuid.UUID,
    body: CommentCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    page = await _readable_page(session, page_id, user)  # 对页有读权限即可评论
    c = await comment_repo.create(session, page_id=page_id, author_id=user.id, body=body.body)
    await session.flush()
    await audit_service.record(
        session, actor_id=user.id, action="comment.create", target_type="page", target_id=page_id
    )
    await notification_service.notify_watchers(
        session, page_id=page_id, actor_id=user.id, type="page.commented",
        message=f"{user.display_name} 评论了《{page.title}》",
    )
    await session.commit()
    return _out(c, user.display_name)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    c = await comment_repo.get_by_id(session, comment_id)
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comment not found")
    # 仅作者本人或管理员可删
    if c.author_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not allowed")
    await comment_repo.delete(session, comment_id)
    await audit_service.record(
        session, actor_id=user.id, action="comment.delete", target_type="comment", target_id=comment_id
    )
    await session.commit()
