from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.activity import ActivityItem
from app.services import activity_service

router = APIRouter(tags=["activity"])


@router.get("/activity", response_model=Response[list[ActivityItem]])
@api_response
async def activity(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """可见知识库内的最近动态：页面更新 + 评论，按时间倒序合并。"""
    return await activity_service.list_activity(session, user)
