import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.controllers import (
    audit,
    auth,
    comments,
    favorites,
    health,
    kb,
    org,
    query,
    reviews,
    search,
    sources,
    stats,
    wiki,
)
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware

_error_logger = logging.getLogger("app.error")


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="LLM Wiki API")
    # CORS 先加（内层），RequestContext 后加（外层）：request_id 最先设置、最后给响应补头
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        """兜底未捕获异常：完整堆栈进服务端日志，对外只返回 request_id，不泄漏内部细节。"""
        rid = getattr(request.state, "request_id", "-")
        _error_logger.exception("未处理异常 rid=%s %s %s", rid, request.method, request.url.path)
        return JSONResponse(
            status_code=500, content={"detail": "internal server error", "request_id": rid}
        )

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(org.router, prefix="/api")
    app.include_router(kb.router, prefix="/api")
    app.include_router(sources.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(query.router, prefix="/api")
    app.include_router(wiki.router, prefix="/api")
    app.include_router(comments.router, prefix="/api")
    app.include_router(favorites.router, prefix="/api")
    app.include_router(reviews.router, prefix="/api")
    app.include_router(audit.router, prefix="/api")
    app.include_router(stats.router, prefix="/api")
    return app


app = create_app()
