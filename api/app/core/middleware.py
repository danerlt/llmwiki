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
from starlette.responses import JSONResponse, Response

from app.core import metrics
from app.core.config import settings

# 当前请求的 id，供日志格式化与全局异常处理读取（无请求上下文时为 "-"）
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

_access_logger = logging.getLogger("app.access")

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-XSS-Protection": "0",
}


# 进程内固定窗口限流计数：{(ip, 分钟窗口): 次数}。多实例需换 Redis；探针路径豁免。
_rl_store: dict[tuple[str, int], int] = {}
_RL_EXEMPT = {"/api/health", "/api/readyz", "/api/metrics"}


def reset_rate_limit() -> None:
    _rl_store.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按客户端 IP 的每分钟固定窗口限流。settings.rate_limit_per_min<=0 时关闭（默认关闭）。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        limit = settings.rate_limit_per_min
        if limit <= 0 or request.method == "OPTIONS" or request.url.path in _RL_EXEMPT:
            return await call_next(request)
        ip = request.client.host if request.client else "anon"
        window = int(time.time()) // 60
        # 清理过期窗口，避免无界增长
        for k in [k for k in _rl_store if k[1] != window]:
            del _rl_store[k]
        key = (ip, window)
        _rl_store[key] = _rl_store.get(key, 0) + 1
        if _rl_store[key] > limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)


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
        metrics.observe(request.method, response.status_code, dur_ms / 1000)
        response.headers["X-Request-ID"] = rid
        for key, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response
