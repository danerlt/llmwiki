import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PromotionRequest, User
from app.repositories import kb_repo, promotion_repo, user_repo, wiki_repo
from app.services import kb_service, permission_service


async def request_promotion(
    session: AsyncSession,
    requester: User,
    page_id: uuid.UUID,
    to_kb_id: uuid.UUID,
    note: str | None = None,
) -> PromotionRequest:
    """发起晋升申请。铁律：申请人必须能读到源页，且必须能访问目标 KB——
    不能把内容投送进自己都看不到的平级/无关作用域（跨作用域泄漏/投毒）。"""
    page = await wiki_repo.get_by_id(session, page_id)
    if page is None:
        raise LookupError("page not found")
    accessible = await permission_service.accessible_kb_ids(session, requester)
    if page.kb_id not in accessible:
        raise PermissionError("cannot promote a page you cannot read")
    if await kb_repo.get_by_id(session, to_kb_id) is None:
        raise LookupError("target kb not found")
    if to_kb_id not in accessible:
        raise PermissionError("cannot promote into a knowledge base you cannot access")
    return await promotion_repo.create(
        session, page_id=page_id, to_kb_id=to_kb_id, requested_by=requester.id, note=note
    )


async def get(session: AsyncSession, pr_id: uuid.UUID) -> PromotionRequest | None:
    return await promotion_repo.get_by_id(session, pr_id)


async def list_reviewable(session: AsyncSession, reviewer: User) -> list[PromotionRequest]:
    """只返回审核者对其目标 KB 有写权限的待审请求（公司/部门→admin、团队→成员）。"""
    out: list[PromotionRequest] = []
    for pr in await promotion_repo.list_pending(session):
        kb = await kb_repo.get_by_id(session, pr.to_kb_id)
        if kb is not None and await permission_service.can_write(session, reviewer, kb):
            out.append(pr)
    return out


async def approve(session: AsyncSession, reviewer: User, pr_id: uuid.UUID) -> PromotionRequest:
    """批准：审核者须对目标 KB 有写权限；将源页复制到目标 KB 并重建其 index。"""
    pr = await promotion_repo.get_by_id(session, pr_id)
    if pr is None or pr.status != "pending":
        raise LookupError("request not found or already decided")
    kb = await kb_repo.get_by_id(session, pr.to_kb_id)
    if kb is None or not await permission_service.can_write(session, reviewer, kb):
        raise PermissionError("no write permission on target kb")
    page = await wiki_repo.get_by_id(session, pr.page_id)
    if page is None:
        raise LookupError("source page gone")
    # 纵深防御：按【申请人】当前可见域复核晋升合法性，挡住绕过 request_promotion
    # 造出的、或作用域漂移后变得跨作用域的脏请求——审批者写权限不足以授权跨域复制。
    requester = await user_repo.get_by_id(session, pr.requested_by)
    requester_scope = (
        await permission_service.accessible_kb_ids(session, requester) if requester else set()
    )
    if page.kb_id not in requester_scope or pr.to_kb_id not in requester_scope:
        raise PermissionError("promotion violates requester scope invariant")
    await wiki_repo.upsert(
        session,
        kb_id=pr.to_kb_id,
        slug=page.slug,
        title=page.title,
        page_type=page.page_type,
        content_md=page.content_md,
        frontmatter={**(page.frontmatter or {}), "promoted_from": str(page.kb_id)},
        source_ids=list(page.source_ids or []),
    )
    await session.flush()
    await kb_service.rebuild_index(session, pr.to_kb_id)
    pr.status = "approved"
    pr.reviewer_id = reviewer.id
    pr.decided_at = datetime.now(timezone.utc)
    return pr


async def reject(
    session: AsyncSession, reviewer: User, pr_id: uuid.UUID, note: str | None = None
) -> PromotionRequest:
    pr = await promotion_repo.get_by_id(session, pr_id)
    if pr is None or pr.status != "pending":
        raise LookupError("request not found or already decided")
    kb = await kb_repo.get_by_id(session, pr.to_kb_id)
    if kb is None or not await permission_service.can_write(session, reviewer, kb):
        raise PermissionError("no write permission on target kb")
    pr.status = "rejected"
    pr.reviewer_id = reviewer.id
    pr.note = note or pr.note
    pr.decided_at = datetime.now(timezone.utc)
    return pr
