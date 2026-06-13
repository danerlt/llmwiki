"""请求上下文与安全响应头中间件。

- 为每个请求生成/透传 X-Request-ID，存入 request.state 与 contextvar（供日志/异常处理关联）。
- 给所有响应补一组安全响应头（OWASP/渗透测试基线常查项）。
"""

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# 当前请求的 id，供日志格式化与全局异常处理读取（无请求上下文时为 "-"）
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

_access_logger = logging.getLogger("app.access")

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-XSS-Protection": "0",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = rid
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        dur_ms = (time.perf_counter() - start) * 1000
        _access_logger.info(
            "%s %s -> %s %.1fms", request.method, request.url.path, response.status_code, dur_ms
        )
        response.headers["X-Request-ID"] = rid
        for key, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response
