import httpx
import pytest

from app.integrations.llm import LLMClient
from app.integrations.storage import MinioStorage, StorageBackend
from tests.fakes import FakeStorage


def test_fake_storage_satisfies_protocol():
    s: StorageBackend = FakeStorage()
    s.put("k", b"hi", "text/plain")
    assert s.get("k") == b"hi"
    assert s.presigned_url("k").startswith("memory://")


def test_minio_storage_constructs_without_connecting():
    # 仅构造，不发起网络请求
    store = MinioStorage(
        endpoint="minio:9000", access_key="x", secret_key="y",
        bucket="sources", secure=False,
    )
    assert store.bucket == "sources"


def test_llm_client_constructs():
    c = LLMClient(base_url="http://llm", api_key="k", model="m")
    assert c.model == "m"


@pytest.mark.asyncio
async def test_llm_retries_on_5xx_then_succeeds():
    n = {"calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["calls"] += 1
        if n["calls"] == 1:
            return httpx.Response(503, json={"error": "busy"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"total_tokens": 7},
            },
        )

    c = LLMClient(
        base_url="http://llm", api_key="k", model="m",
        max_retries=2, backoff_base=0, transport=httpx.MockTransport(handler),
    )
    assert await c.complete("s", "u") == "ok"
    assert n["calls"] == 2  # 第一次 503 → 重试成功


@pytest.mark.asyncio
async def test_llm_does_not_retry_on_4xx():
    n = {"calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["calls"] += 1
        return httpx.Response(400, json={"error": "bad request"})

    c = LLMClient(
        base_url="http://llm", api_key="k", model="m",
        max_retries=3, backoff_base=0, transport=httpx.MockTransport(handler),
    )
    with pytest.raises(httpx.HTTPStatusError):
        await c.complete("s", "u")
    assert n["calls"] == 1  # 4xx 客户端错误不重试
