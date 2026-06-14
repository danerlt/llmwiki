"""@api_response 装饰器：把控制器的普通返回值包进 Response 信封并注入 request_id。

用法：
    @router.get("/kbs", response_model=Response[list[KBOut]])
    @api_response
    async def list_my_kbs(...) -> list[KBOut]:
        return [...]

控制器仍返回业务数据（list/dict/schema），无需关心信封；已是 Response 的则透传。
"""
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

from app.common.response import Response
from app.core.middleware import request_id_ctx

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def api_response(func: F) -> F:
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Response:
        result = await func(*args, **kwargs)
        if isinstance(result, Response):
            if result.request_id is None:
                result.request_id = request_id_ctx.get()
            return result
        return Response.ok(data=result, request_id=request_id_ctx.get())

    return wrapper  # type: ignore[return-value]
