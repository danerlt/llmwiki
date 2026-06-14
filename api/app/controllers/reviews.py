import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.promotion import PromotionCreate, PromotionOut, ReviewDecision
from app.services import promotion_service

router = APIRouter(tags=["reviews"])


@router.post("/pages/{page_id}/promote", response_model=Response[PromotionOut])
@api_response
async def promote(
    page_id: uuid.UUID,
    body: PromotionCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await promotion_service.promote(
        session, user, page_id, body.to_kb_id, note=body.note
    )


@router.get("/reviews", response_model=Response[list[PromotionOut]])
@api_response
async def list_reviews(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
):
    return await promotion_service.list_reviews(session, user)


@router.post("/reviews/{pr_id}/approve", response_model=Response[PromotionOut])
@api_response
async def approve(
    pr_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await promotion_service.approve_request(session, user, pr_id)


@router.post("/reviews/{pr_id}/reject", response_model=Response[PromotionOut])
@api_response
async def reject(
    pr_id: uuid.UUID,
    body: ReviewDecision,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await promotion_service.reject_request(session, user, pr_id, note=body.note)
