"""全局异常处理：把 AppException 子类统一转成"对应 HTTP 状态码 + 信封"。

仅接管 AppException 树；FastAPI 原生 HTTPException 与未捕获异常的既有行为不在此改动
（控制器全量迁移到信封是阶段5的事），保证阶段3 灰度期间存量端点行为不变。
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.common.exceptions import AppException
from app.common.response import Response
from app.core.middleware import request_id_ctx


def register_exception(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def _handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        rid = getattr(request.state, "request_id", None) or request_id_ctx.get()
        envelope = Response.fail(code=exc.code, message=exc.message, request_id=rid)
        return JSONResponse(status_code=exc.http_status, content=envelope.model_dump())
