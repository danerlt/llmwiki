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
