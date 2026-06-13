import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import PromotionRequest, User
from app.repositories import kb_repo, wiki_repo
from app.schemas.promotion import PromotionCreate, PromotionOut, ReviewDecision
from app.services import promotion_service

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


@router.post("/pages/{page_id}/promote", response_model=PromotionOut)
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
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await session.commit()
    return await _to_out(session, pr)


@router.get("/reviews", response_model=list[PromotionOut])
async def list_reviews(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
):
    prs = await promotion_service.list_reviewable(session, user)
    return [await _to_out(session, pr) for pr in prs]


@router.post("/reviews/{pr_id}/approve", response_model=PromotionOut)
async def approve(
    pr_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        pr = await promotion_service.approve(session, user, pr_id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await session.commit()
    return await _to_out(session, pr)


@router.post("/reviews/{pr_id}/reject", response_model=PromotionOut)
async def reject(
    pr_id: uuid.UUID,
    body: ReviewDecision,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        pr = await promotion_service.reject(session, user, pr_id, note=body.note)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await session.commit()
    return await _to_out(session, pr)
