import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.api_response import api_response
from app.common.exceptions import NotFoundException
from app.common.response import Response
from app.core.deps import require_admin
from app.db.session import get_db
from app.models import User
from app.repositories import webhook_repo
from app.schemas.webhook import WebhookCreate, WebhookOut
from app.services import audit_service

router = APIRouter(tags=["webhooks"], dependencies=[Depends(require_admin)])


@router.get("/webhooks", response_model=Response[list[WebhookOut]])
@api_response
async def list_webhooks(session: AsyncSession = Depends(get_db)):
    return await webhook_repo.list_all(session)


@router.post("/webhooks", response_model=Response[WebhookOut], status_code=status.HTTP_201_CREATED)
@api_response
async def create_webhook(
    body: WebhookCreate,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    w = await webhook_repo.create(session, created_by=actor.id, url=body.url, secret=body.secret)
    await audit_service.record(
        session, actor_id=actor.id, action="webhook.create", target_type="webhook",
        target_id=w.id, detail={"url": body.url},
    )
    await session.commit()
    return w


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
@api_response
async def delete_webhook(
    webhook_id: uuid.UUID,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    w = await webhook_repo.get_by_id(session, webhook_id)
    if w is None:
        raise NotFoundException("webhook not found")
    await session.delete(w)
    await audit_service.record(
        session, actor_id=actor.id, action="webhook.delete", target_type="webhook",
        target_id=webhook_id,
    )
    await session.commit()
