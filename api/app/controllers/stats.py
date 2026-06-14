from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.wiki import StatsOut
from app.services.stats_service import stats_service

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=Response[StatsOut])
@api_response
async def stats(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return await stats_service.overview(session, user)
