import hashlib
import hmac
import json
import logging
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundException
from app.models import User
from app.repositories import webhook_repo
from app.schemas.webhook import WebhookCreate, WebhookOut
from app.services.audit_service import audit_service

_logger = logging.getLogger("app.webhook")


class WebhookService:
    async def list_webhooks(self, session: AsyncSession) -> list[WebhookOut]:
        rows = await webhook_repo.list_all(session)
        return [WebhookOut.model_validate(r) for r in rows]

    async def create_webhook(
        self, session: AsyncSession, actor: User, body: WebhookCreate
    ) -> WebhookOut:
        w = await webhook_repo.create(
            session, created_by=actor.id, url=body.url, secret=body.secret
        )
        await audit_service.record(
            session, actor_id=actor.id, action="webhook.create", target_type="webhook",
            target_id=w.id, detail={"url": body.url},
        )
        await session.commit()
        return WebhookOut.model_validate(w)

    async def delete_webhook(
        self, session: AsyncSession, actor: User, webhook_id: uuid.UUID
    ) -> None:
        w = await webhook_repo.get_by_id(session, webhook_id)
        if w is None:
            raise NotFoundException("webhook not found")
        await session.delete(w)
        await audit_service.record(
            session, actor_id=actor.id, action="webhook.delete", target_type="webhook",
            target_id=webhook_id,
        )
        await session.commit()

    def sign(self, secret: str, body: bytes) -> str:
        """HMAC-SHA256 签名，接收方据此验证来源与完整性。"""
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    async def dispatch(self, session: AsyncSession, event: str, payload: dict) -> None:
        """向所有启用的 webhook best-effort 投递（失败仅记日志，不影响主流程）。"""
        hooks = await webhook_repo.list_active(session)
        if not hooks:
            return
        body = json.dumps({"event": event, "data": payload}, ensure_ascii=False).encode()
        async with httpx.AsyncClient(timeout=5) as client:
            for h in hooks:
                try:
                    await client.post(
                        h.url,
                        content=body,
                        headers={
                            "Content-Type": "application/json",
                            "X-Lumen-Event": event,
                            "X-Lumen-Signature": self.sign(h.secret, body),
                        },
                    )
                except Exception:  # noqa: BLE001 — 投递失败不影响主业务
                    _logger.warning("webhook 投递失败 url=%s event=%s", h.url, event)


webhook_service = WebhookService()
