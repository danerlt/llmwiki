import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories import api_key_repo
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.services import api_key_service, audit_service

router = APIRouter(tags=["api-keys"])


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_keys(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await api_key_repo.list_by_user(session, user.id)


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: ApiKeyCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    rec, raw = await api_key_service.issue(session, user_id=user.id, name=body.name)
    await audit_service.record(
        session, actor_id=user.id, action="apikey.create", target_type="api_key",
        target_id=rec.id, detail={"name": body.name},
    )
    await session.commit()
    return ApiKeyCreated(
        id=rec.id, name=rec.name, prefix=rec.prefix, revoked=rec.revoked,
        created_at=rec.created_at, last_used_at=rec.last_used_at, key=raw,
    )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    rec = await api_key_repo.get_owned(session, key_id, user.id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="key not found")
    rec.revoked = True
    await audit_service.record(
        session, actor_id=user.id, action="apikey.revoke", target_type="api_key", target_id=key_id
    )
    await session.commit()
