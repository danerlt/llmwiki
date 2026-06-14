"""arq 入队池单例化。"""
from app.worker import queue


async def test_get_pool_is_singleton(monkeypatch):
    queue._pool = None  # 重置全局缓存
    calls: list[int] = []

    async def _fake_create_pool(_settings):
        calls.append(1)
        return object()  # 哨兵 pool，避免真连 Redis

    monkeypatch.setattr(queue, "create_pool", _fake_create_pool)
    try:
        p1 = await queue.get_pool()
        p2 = await queue.get_pool()
        assert p1 is p2  # 复用同一个 pool
        assert len(calls) == 1  # 只建一次
    finally:
        queue._pool = None


async def test_enqueue_ingest_uses_pool(monkeypatch):
    queue._pool = None
    enqueued: list[str] = []

    class _Job:
        job_id = "job-1"

    class _FakePool:
        async def enqueue_job(self, fn, arg):
            enqueued.append((fn, arg))
            return _Job()

    async def _fake_create_pool(_settings):
        return _FakePool()

    monkeypatch.setattr(queue, "create_pool", _fake_create_pool)
    try:
        job_id = await queue.enqueue_ingest("src-123")
        assert job_id == "job-1"
        assert enqueued == [("ingest_source", "src-123")]
    finally:
        queue._pool = None
