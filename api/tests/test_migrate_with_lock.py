"""启动迁移的 Redis 分布式锁逻辑。"""
import fakeredis

from app.db import migrate_with_lock as m


def test_migrate_acquires_lock_runs_and_releases(monkeypatch):
    fake = fakeredis.FakeRedis()
    ran: list[int] = []
    monkeypatch.setattr(m, "_run_alembic_upgrade", lambda: ran.append(1))
    m.main(client=fake)
    assert ran == [1]  # 抢到锁 → 跑迁移
    assert fake.get(m._LOCK_KEY) is None  # 跑完释放锁


def test_migrate_waits_and_skips_when_lock_held(monkeypatch):
    fake = fakeredis.FakeRedis()
    fake.set(m._LOCK_KEY, "held")  # 另一副本已持锁
    ran: list[int] = []
    monkeypatch.setattr(m, "_run_alembic_upgrade", lambda: ran.append(1))

    def _fake_sleep(_s):  # 模拟持锁副本迁移完成、释放锁
        fake.delete(m._LOCK_KEY)

    monkeypatch.setattr(m.time, "sleep", _fake_sleep)
    m.main(client=fake)
    assert ran == []  # 没抢到锁 → 等待, 不重复跑迁移
