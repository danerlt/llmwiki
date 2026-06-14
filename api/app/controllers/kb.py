from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.kb import KBOut
from app.services import kb_service

router = APIRouter(tags=["kb"])


@router.get("/kbs", response_model=Response[list[KBOut]])
@api_response
async def list_my_kbs(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return await kb_service.list_my_kbs(session, user)
