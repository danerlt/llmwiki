"""启动迁移的 Redis 分布式锁逻辑（含审查加固：CAS 释放 + 等待方兜底重跑）。"""
import fakeredis

from app.db import migrate_with_lock as m


def test_migrate_acquires_lock_runs_and_releases(monkeypatch):
    fake = fakeredis.FakeRedis()
    ran: list[int] = []
    monkeypatch.setattr(m, "_run_alembic_upgrade", lambda: ran.append(1))
    m.main(client=fake)
    assert ran == [1]  # 抢到锁 → 跑迁移
    assert fake.get(m._LOCK_KEY) is None  # 跑完 CAS 释放


def test_waiter_reruns_migration_after_holder_releases(monkeypatch):
    fake = fakeredis.FakeRedis()
    fake.set(m._LOCK_KEY, "holder-token")  # 另一副本持锁
    ran: list[int] = []
    monkeypatch.setattr(m, "_run_alembic_upgrade", lambda: ran.append(1))

    def _fake_sleep(_s):  # 模拟持锁者迁移完成、释放锁
        fake.delete(m._LOCK_KEY)

    monkeypatch.setattr(m.time, "sleep", _fake_sleep)
    m.main(client=fake)
    # 锁释放后等待方自己抢锁重跑(幂等), 保证库确实迁到 head 才放行
    assert ran == [1]
    assert fake.get(m._LOCK_KEY) is None


def test_release_only_deletes_own_lock(monkeypatch):
    fake = fakeredis.FakeRedis()

    def _run():  # 模拟迁移耗时超 TTL, 锁被另一副本抢走
        fake.set(m._LOCK_KEY, "other-replica-token")

    monkeypatch.setattr(m, "_run_alembic_upgrade", _run)
    assert m._try_migrate_once(fake) is True  # 自己抢到并跑
    assert fake.get(m._LOCK_KEY) == b"other-replica-token"  # CAS 没误删他人锁
