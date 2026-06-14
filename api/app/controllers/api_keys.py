import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.services import api_key_service

router = APIRouter(tags=["api-keys"])


@router.get("/api-keys", response_model=Response[list[ApiKeyOut]])
@api_response
async def list_keys(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await api_key_service.list_my_keys(session, user)


@router.post("/api-keys", response_model=Response[ApiKeyCreated], status_code=status.HTTP_201_CREATED)
@api_response
async def create_key(
    body: ApiKeyCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await api_key_service.create_key(session, user, body.name)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
@api_response
async def revoke_key(
    key_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await api_key_service.revoke_key(session, user, key_id)
