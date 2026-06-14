import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ParamsException,
)
from app.ingest import parser, pipeline
from app.models import User
from app.repositories import (
    favorite_repo,
    kb_repo,
    source_repo,
    subscription_repo,
    user_repo,
    wiki_repo,
)
from app.schemas.wiki import (
    HUMAN_PAGE_TYPES,
    PageCreate,
    PageDetailOut,
    PageOut,
    PageUpdate,
    PageVersionOut,
    SourceRef,
)
from app.services.audit_service import audit_service
from app.services.kb_service import kb_service
from app.services.notification_service import notification_service
from app.services.permission_service import permission_service
from app.services.webhook_service import webhook_service


class WikiService:
    """Wiki 页面：CRUD、版本、认证、导出。repo 调用/权限/业务/commit 全在此。"""

    async def _build_detail(
        self,
        session: AsyncSession,
        page,
        accessible: set[uuid.UUID],
        *,
        is_favorited: bool = False,
        is_subscribed: bool = False,
    ) -> PageDetailOut:
        backlinks = [b for b in await wiki_repo.backlinks(session, page.id) if b.kb_id in accessible]
        outlinks = [o for o in await wiki_repo.outlinks(session, page.id) if o.kb_id in accessible]
        src_ids: list[uuid.UUID] = []
        for s in page.source_ids or []:
            try:
                src_ids.append(uuid.UUID(str(s)))
            except (ValueError, TypeError):
                pass
        # 仅返回可见 KB 的来源——晋升等路径可能让页的 source_ids 指向跨作用域的 Source，
        # 与 backlinks/outlinks 的可见性过滤保持一致，避免泄漏他人作用域的源文件名。
        sources = [
            s for s in await source_repo.list_by_ids(session, src_ids) if s.kb_id in accessible
        ]
        verifier_name = None
        if page.verified_by:
            v = await user_repo.get_by_id(session, page.verified_by)
            verifier_name = v.display_name if v else None
        return PageDetailOut(
            id=page.id,
            kb_id=page.kb_id,
            title=page.title,
            slug=page.slug,
            page_type=page.page_type,
            content_md=page.content_md,
            frontmatter=page.frontmatter or {},
            source_ids=[str(s) for s in (page.source_ids or [])],
            updated_at=page.updated_at,
            verified_at=page.verified_at,
            verified_by_name=verifier_name,
            is_favorited=is_favorited,
            is_subscribed=is_subscribed,
            backlinks=[
                PageOut(id=b.id, kb_id=b.kb_id, title=b.title, slug=b.slug, page_type=b.page_type)
                for b in backlinks
            ],
            outlinks=[
                PageOut(id=o.id, kb_id=o.kb_id, title=o.title, slug=o.slug, page_type=o.page_type)
                for o in outlinks
            ],
            sources=[SourceRef(id=s.id, filename=s.filename) for s in sources],
            tags=list(page.tags or []),
        )

    async def _writable_page(self, session: AsyncSession, page_id: uuid.UUID, user: User):
        """取页并校验当前用户对其所在 KB 有写权限，否则 404/403。"""
        page = await wiki_repo.get_by_id(session, page_id)
        if page is None:
            raise NotFoundException("page not found")
        kb = await kb_repo.get_by_id(session, page.kb_id)
        if kb is None or not await permission_service.can_write(session, user, kb):
            raise ForbiddenException("no write permission")
        return page

    async def _post_write_rebuild(self, session: AsyncSession, page, content_md: str) -> None:
        """统一的写后处理：刷新链接图 + 重建 index 目录 + 回填 wikilink 目标。"""
        await wiki_repo.replace_links(
            session, from_page_id=page.id, to_slugs=pipeline.extract_wikilinks(content_md or "")
        )
        await session.flush()
        await kb_service.rebuild_index(session, page.kb_id)
        await wiki_repo.backfill_link_targets(session, kb_id=page.kb_id)

    async def list_pages(
        self, session: AsyncSession, user: User, kb_id: uuid.UUID, tag: str | None = None
    ) -> list[PageOut]:
        accessible = await permission_service.accessible_kb_ids(session, user)
        if kb_id not in accessible:
            raise ForbiddenException("no access")
        pages = await wiki_repo.list_by_kb(session, kb_id)
        if tag:
            pages = [p for p in pages if tag in (p.tags or [])]
        return [PageOut.model_validate(p) for p in pages]

    async def create_page(
        self, session: AsyncSession, user: User, kb_id: uuid.UUID, body: PageCreate
    ) -> PageDetailOut:
        kb = await kb_repo.get_by_id(session, kb_id)
        if kb is None:
            raise NotFoundException("kb not found")
        if not await permission_service.can_write(session, user, kb):
            raise ForbiddenException("no write permission")
        if body.page_type not in HUMAN_PAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"page_type must be one of {HUMAN_PAGE_TYPES}",
            )
        slug = parser.slugify(body.slug or body.title)
        if not slug:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid slug"
            )
        if await wiki_repo.get_by_slug(session, kb_id, slug) is not None:
            raise ConflictException("slug already exists")
        page = await wiki_repo.upsert(
            session, kb_id=kb_id, slug=slug, title=body.title, page_type=body.page_type,
            content_md=body.content_md, frontmatter={"author": str(user.id)}, source_ids=[],
        )
        page.tags = [t.strip() for t in body.tags if t.strip()]
        await session.flush()
        await wiki_repo.add_version(session, page, edited_by=user.id)  # v1 = 初始内容
        await self._post_write_rebuild(session, page, body.content_md)
        await audit_service.record(
            session, actor_id=user.id, action="page.create", target_type="page",
            target_id=page.id, detail={"kb_id": str(kb_id), "slug": slug},
        )
        await session.commit()
        accessible = await permission_service.accessible_kb_ids(session, user)
        return await self._build_detail(session, page, accessible)

    async def update_page(
        self, session: AsyncSession, user: User, page_id: uuid.UUID, body: PageUpdate
    ) -> PageDetailOut:
        page = await self._writable_page(session, page_id, user)
        if body.page_type is not None and body.page_type not in HUMAN_PAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"page_type must be one of {HUMAN_PAGE_TYPES}",
            )
        if body.title is not None:
            page.title = body.title
        if body.content_md is not None:
            page.content_md = body.content_md
        if body.page_type is not None:
            page.page_type = body.page_type
        if body.tags is not None:
            page.tags = [t.strip() for t in body.tags if t.strip()]
        await session.flush()
        await wiki_repo.add_version(session, page, edited_by=user.id)  # 每次保存留版本
        await self._post_write_rebuild(session, page, page.content_md or "")
        await audit_service.record(
            session, actor_id=user.id, action="page.update", target_type="page",
            target_id=page.id, detail={"kb_id": str(page.kb_id)},
        )
        await notification_service.notify_watchers(
            session, page_id=page.id, actor_id=user.id, type="page.updated",
            message=f"{user.display_name} 编辑了《{page.title}》",
        )
        await webhook_service.dispatch(
            session, "page.updated",
            {"page_id": str(page.id), "title": page.title, "actor": user.display_name},
        )
        await session.commit()
        accessible = await permission_service.accessible_kb_ids(session, user)
        return await self._build_detail(session, page, accessible)

    async def delete_page(self, session: AsyncSession, user: User, page_id: uuid.UUID) -> None:
        page = await self._writable_page(session, page_id, user)
        if page.page_type == "index":
            raise ParamsException("cannot delete the index page")
        kb_id = page.kb_id
        slug = page.slug
        await wiki_repo.delete_page(session, page_id)
        await session.flush()
        await kb_service.rebuild_index(session, kb_id)
        await audit_service.record(
            session, actor_id=user.id, action="page.delete", target_type="page",
            target_id=page_id, detail={"kb_id": str(kb_id), "slug": slug},
        )
        await session.commit()

    async def list_versions(
        self, session: AsyncSession, user: User, page_id: uuid.UUID
    ) -> list[PageVersionOut]:
        page = await wiki_repo.get_by_id(session, page_id)
        if page is None:
            raise NotFoundException("page not found")
        accessible = await permission_service.accessible_kb_ids(session, user)
        if page.kb_id not in accessible:
            raise ForbiddenException("no access")
        versions = await wiki_repo.list_versions(session, page_id)
        return [PageVersionOut.model_validate(v) for v in versions]

    async def revert_page(
        self, session: AsyncSession, user: User, page_id: uuid.UUID, version_no: int
    ) -> PageDetailOut:
        page = await self._writable_page(session, page_id, user)
        target = await wiki_repo.get_version(session, page_id, version_no)
        if target is None:
            raise NotFoundException("version not found")
        page.title = target.title
        page.content_md = target.content_md
        page.page_type = target.page_type
        await session.flush()
        await wiki_repo.add_version(session, page, edited_by=user.id)  # 回滚也留痕（新版本）
        await self._post_write_rebuild(session, page, page.content_md or "")
        await audit_service.record(
            session, actor_id=user.id, action="page.revert", target_type="page",
            target_id=page.id, detail={"kb_id": str(page.kb_id), "to_version": version_no},
        )
        await session.commit()
        accessible = await permission_service.accessible_kb_ids(session, user)
        return await self._build_detail(session, page, accessible)

    async def export_markdown(
        self, session: AsyncSession, user: User, page_id: uuid.UUID
    ) -> tuple[str, str]:
        """导出页面为 Markdown：返回 (正文, slug)。需读权限；下载 Response 由 controller 构造。"""
        page = await wiki_repo.get_by_id(session, page_id)
        if page is None:
            raise NotFoundException("page not found")
        accessible = await permission_service.accessible_kb_ids(session, user)
        if page.kb_id not in accessible:
            raise ForbiddenException("no access")
        body = f"# {page.title}\n\n{page.content_md or ''}\n"
        return body, page.slug

    async def verify_page(
        self, session: AsyncSession, user: User, page_id: uuid.UUID
    ) -> PageDetailOut:
        """认证页面为权威内容（专家背书）。需对该页有写权限。"""
        page = await self._writable_page(session, page_id, user)
        page.verified_by = user.id
        page.verified_at = datetime.now(timezone.utc)
        await audit_service.record(
            session, actor_id=user.id, action="page.verify", target_type="page", target_id=page.id
        )
        await session.commit()
        await session.refresh(page)  # 重载 server onupdate 的 updated_at，避免同步构造触发 lazy load
        accessible = await permission_service.accessible_kb_ids(session, user)
        return await self._build_detail(session, page, accessible)

    async def unverify_page(
        self, session: AsyncSession, user: User, page_id: uuid.UUID
    ) -> PageDetailOut:
        page = await self._writable_page(session, page_id, user)
        page.verified_by = None
        page.verified_at = None
        await audit_service.record(
            session, actor_id=user.id, action="page.unverify", target_type="page", target_id=page.id
        )
        await session.commit()
        await session.refresh(page)
        accessible = await permission_service.accessible_kb_ids(session, user)
        return await self._build_detail(session, page, accessible)

    async def recent_pages(self, session: AsyncSession, user: User) -> list[PageOut]:
        ids = await permission_service.accessible_kb_ids(session, user)
        rows = await wiki_repo.recent(session, list(ids), limit=8)
        return [PageOut.model_validate(p) for p in rows]

    async def get_page(
        self, session: AsyncSession, user: User, page_id: uuid.UUID
    ) -> PageDetailOut:
        page = await wiki_repo.get_by_id(session, page_id)
        if page is None:
            raise NotFoundException("page not found")
        accessible = await permission_service.accessible_kb_ids(session, user)
        if page.kb_id not in accessible:
            raise ForbiddenException("no access")
        fav = await favorite_repo.exists(session, user_id=user.id, page_id=page.id)
        sub = await subscription_repo.exists(session, user_id=user.id, page_id=page.id)
        return await self._build_detail(
            session, page, accessible, is_favorited=fav, is_subscribed=sub
        )


wiki_service = WikiService()
