from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import kb_repo, wiki_repo
from app.schemas.kb import KBOut
from app.services import permission_service

router = APIRouter(tags=["kb"])


@router.get("/kbs", response_model=Response[list[KBOut]])
@api_response
async def list_my_kbs(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    id_list = list(await permission_service.accessible_kb_ids(session, user))
    kbs = await kb_repo.list_by_ids(session, id_list)
    counts = await wiki_repo.counts_by_kbs(session, id_list)
    return [
        KBOut(
            id=k.id,
            scope_type=k.scope_type,
            scope_ref_id=k.scope_ref_id,
            name=k.name,
            page_count=counts.get(k.id, 0),
        )
        for k in kbs
    ]
