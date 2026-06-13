from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import kb_repo
from app.schemas.kb import KBOut
from app.services import permission_service

router = APIRouter(tags=["kb"])


@router.get("/kbs", response_model=list[KBOut])
async def list_my_kbs(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    ids = await permission_service.accessible_kb_ids(session, user)
    return await kb_repo.list_by_ids(session, list(ids))
