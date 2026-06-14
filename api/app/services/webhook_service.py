import hashlib
import hmac
import json
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import webhook_repo

_logger = logging.getLogger("app.webhook")


class WebhookService:
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
