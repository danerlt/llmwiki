"""阶段3 统一响应信封 + 异常基础设施的单元/集成测试。"""
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.common.api_response import api_response
from app.common.exception_handler import register_exception
from app.common.exceptions import AppException, ErrorCode, ForbiddenException, NotFoundException
from app.common.response import Response


def test_response_ok_envelope():
    r = Response.ok(data={"x": 1}, request_id="rid1")
    d = r.model_dump()
    assert d["success"] is True
    assert d["code"] == "0"
    assert d["data"] == {"x": 1}
    assert d["request_id"] == "rid1"


def test_response_fail_envelope():
    r = Response.fail(code=ErrorCode.NOT_FOUND, message="not found", request_id="r2")
    d = r.model_dump()
    assert d["success"] is False
    assert d["code"] == "404"
    assert d["message"] == "not found"
    assert d["data"] is None


def test_appexception_subclasses_carry_code_and_status():
    exc = NotFoundException("页面不存在")
    assert exc.http_status == 404
    assert exc.code == ErrorCode.NOT_FOUND
    assert exc.message == "页面不存在"
    base = AppException()  # 默认 500
    assert base.http_status == 500
    assert base.code == ErrorCode.INTERNAL


async def test_api_response_wraps_plain_return():
    @api_response
    async def endpoint():
        return {"a": 1}

    result = await endpoint()
    assert isinstance(result, Response)
    assert result.success is True
    assert result.data == {"a": 1}


async def test_api_response_passes_through_existing_response():
    @api_response
    async def endpoint():
        return Response.ok(data=[1, 2], request_id="keep")

    result = await endpoint()
    assert result.request_id == "keep"
    assert result.data == [1, 2]


async def test_register_exception_maps_appexception_to_envelope():
    app2 = FastAPI()
    register_exception(app2)

    @app2.get("/boom")
    async def boom():
        raise ForbiddenException("无权访问")

    transport = ASGITransport(app=app2)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        resp = await ac.get("/boom")
    assert resp.status_code == 403
    body = resp.json()
    assert body["success"] is False
    assert body["code"] == "403"
    assert body["message"] == "无权访问"
    assert body["data"] is None
