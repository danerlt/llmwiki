import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.response import Response
from app.core.deps import require_admin
from app.db.session import get_db
from app.models import User
from app.schemas.webhook import WebhookCreate, WebhookOut
from app.services import webhook_service

router = APIRouter(tags=["webhooks"], dependencies=[Depends(require_admin)])


@router.get("/webhooks", response_model=Response[list[WebhookOut]])
@api_response
async def list_webhooks(session: AsyncSession = Depends(get_db)):
    return await webhook_service.list_webhooks(session)


@router.post("/webhooks", response_model=Response[WebhookOut], status_code=status.HTTP_201_CREATED)
@api_response
async def create_webhook(
    body: WebhookCreate,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    return await webhook_service.create_webhook(session, actor, body)


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
@api_response
async def delete_webhook(
    webhook_id: uuid.UUID,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    return await webhook_service.delete_webhook(session, actor, webhook_id)
