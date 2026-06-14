import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ForbiddenException, NotFoundException
from app.models import Comment, User, WikiPage
from app.repositories import comment_repo, user_repo, wiki_repo
from app.schemas.comment import CommentCreate, CommentOut
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service
from app.services.permission_service import permission_service
from app.services.webhook_service import webhook_service


class CommentService:
    """页面评论：列出/新增/删除，含权限校验与通知/审计/webhook 联动。"""

    async def _readable_page(
        self, session: AsyncSession, page_id: uuid.UUID, user: User
    ) -> WikiPage:
        page = await wiki_repo.get_by_id(session, page_id)
        if page is None:
            raise NotFoundException("page not found")
        accessible = await permission_service.accessible_kb_ids(session, user)
        if page.kb_id not in accessible:
            raise ForbiddenException("no access")
        return page

    def _out(self, c: Comment, name: str) -> CommentOut:
        return CommentOut(
            id=c.id,
            page_id=c.page_id,
            author_id=c.author_id,
            author_name=name,
            body=c.body,
            created_at=c.created_at,
        )

    async def list_comments(
        self, session: AsyncSession, user: User, page_id: uuid.UUID
    ) -> list[CommentOut]:
        await self._readable_page(session, page_id, user)
        out: list[CommentOut] = []
        for c in await comment_repo.list_by_page(session, page_id):
            author = await user_repo.get_by_id(session, c.author_id)
            out.append(self._out(c, author.display_name if author else "(未知)"))
        return out

    async def add_comment(
        self, session: AsyncSession, user: User, page_id: uuid.UUID, body: CommentCreate
    ) -> CommentOut:
        page = await self._readable_page(session, page_id, user)  # 对页有读权限即可评论
        c = await comment_repo.create(
            session, page_id=page_id, author_id=user.id, body=body.body
        )
        await session.flush()
        await audit_service.record(
            session,
            actor_id=user.id,
            action="comment.create",
            target_type="page",
            target_id=page_id,
        )
        await notification_service.notify_watchers(
            session,
            page_id=page_id,
            actor_id=user.id,
            type="page.commented",
            message=f"{user.display_name} 评论了《{page.title}》",
        )
        await webhook_service.dispatch(
            session,
            "page.commented",
            {"page_id": str(page_id), "title": page.title, "actor": user.display_name},
        )
        await session.commit()
        return self._out(c, user.display_name)

    async def delete_comment(
        self, session: AsyncSession, user: User, comment_id: uuid.UUID
    ) -> None:
        c = await comment_repo.get_by_id(session, comment_id)
        if c is None:
            raise NotFoundException("comment not found")
        # 仅作者本人或管理员可删
        if c.author_id != user.id and user.role != "admin":
            raise ForbiddenException("not allowed")
        await comment_repo.delete(session, comment_id)
        await audit_service.record(
            session,
            actor_id=user.id,
            action="comment.delete",
            target_type="comment",
            target_id=comment_id,
        )
        await session.commit()


comment_service = CommentService()
