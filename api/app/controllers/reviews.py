import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.exceptions import ForbiddenException, NotFoundException
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import PromotionRequest, User
from app.repositories import kb_repo, wiki_repo
from app.schemas.promotion import PromotionCreate, PromotionOut, ReviewDecision
from app.services import audit_service, promotion_service

router = APIRouter(tags=["reviews"])


async def _to_out(session: AsyncSession, pr: PromotionRequest) -> PromotionOut:
    page = await wiki_repo.get_by_id(session, pr.page_id)
    kb = await kb_repo.get_by_id(session, pr.to_kb_id)
    return PromotionOut(
        id=pr.id,
        page_id=pr.page_id,
        page_title=page.title if page else "(已删除)",
        to_kb_id=pr.to_kb_id,
        to_kb_name=kb.name if kb else "(未知)",
        requested_by=pr.requested_by,
        status=pr.status,
        note=pr.note,
    )


@router.post("/pages/{page_id}/promote", response_model=Response[PromotionOut])
@api_response
async def promote(
    page_id: uuid.UUID,
    body: PromotionCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        pr = await promotion_service.request_promotion(
            session, user, page_id, body.to_kb_id, note=body.note
        )
        await audit_service.record(
            session, actor_id=user.id, action="promotion.request",
            target_type="page", target_id=page_id, detail={"to_kb_id": str(body.to_kb_id)},
        )
    except PermissionError as e:
        raise ForbiddenException(str(e))
    except LookupError as e:
        raise NotFoundException(str(e))
    await session.commit()
    return await _to_out(session, pr)


@router.get("/reviews", response_model=Response[list[PromotionOut]])
@api_response
async def list_reviews(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
):
    prs = await promotion_service.list_reviewable(session, user)
    return [await _to_out(session, pr) for pr in prs]


@router.post("/reviews/{pr_id}/approve", response_model=Response[PromotionOut])
@api_response
async def approve(
    pr_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        pr = await promotion_service.approve(session, user, pr_id)
        await audit_service.record(
            session, actor_id=user.id, action="promotion.approve",
            target_type="promotion", target_id=pr_id,
        )
    except PermissionError as e:
        raise ForbiddenException(str(e))
    except LookupError as e:
        raise NotFoundException(str(e))
    await session.commit()
    return await _to_out(session, pr)


@router.post("/reviews/{pr_id}/reject", response_model=Response[PromotionOut])
@api_response
async def reject(
    pr_id: uuid.UUID,
    body: ReviewDecision,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        pr = await promotion_service.reject(session, user, pr_id, note=body.note)
        await audit_service.record(
            session, actor_id=user.id, action="promotion.reject",
            target_type="promotion", target_id=pr_id,
        )
    except PermissionError as e:
        raise ForbiddenException(str(e))
    except LookupError as e:
        raise NotFoundException(str(e))
    await session.commit()
    return await _to_out(session, pr)
