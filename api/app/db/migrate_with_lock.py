"""启动时数据库迁移：用 Redis 分布式锁保证多副本(api/worker)不并发跑 alembic。

正确性要点（经对抗式审查加固）：
- **唯一 token + CAS 释放**：锁 value 写唯一 token，释放时只删仍属于自己的锁，避免迁移
  耗时超过 TTL 被他人抢锁后、自己 finally 里误删他人锁。
- **等待方最终自己重跑迁移**：未抢到锁的副本等锁释放后会再抢并自己跑一遍 `alembic upgrade head`
  （幂等，已到 head 即空操作）。这样无论持锁者是正常完成还是崩溃(TTL 被动过期)，最终都有副本
  真正把库迁到 head 才放行，避免"锁消失=迁移完成"的误判带未升级 schema 启动。

容器 command 用法：python -m app.db.migrate_with_lock && uvicorn app.main:app ...
"""
import time
import uuid

import redis
from alembic import command
from alembic.config import Config

from app.core.config import settings

_LOCK_KEY = "llmwiki:migrate:lock"
_LOCK_TTL = 300  # 秒；TTL 防持锁进程崩溃后死锁


def _run_alembic_upgrade() -> None:
    cfg = Config("alembic.ini")  # env.py 用 settings.database_url
    command.upgrade(cfg, "head")


def _wait_redis(client: redis.Redis, retries: int = 60) -> None:
    """等 Redis 就绪（compose depends_on 只保证容器启动, 不保证已可服务）。"""
    for _ in range(retries):
        try:
            client.ping()
            return
        except redis.exceptions.RedisError:
            time.sleep(1)


def _release_own_lock(client: redis.Redis, token: str) -> None:
    """CAS 释放：仅当锁仍是自己写的 token 时才删（fakeredis 无 Lua, 用 get-compare-delete;
    启动期一次性迁移, 非原子窗口可忽略）。"""
    current = client.get(_LOCK_KEY)
    if current is not None and current.decode() == token:
        client.delete(_LOCK_KEY)


def _try_migrate_once(client: redis.Redis) -> bool:
    """抢到锁则自己跑迁移(幂等)并 CAS 释放, 返回 True；没抢到返回 False。"""
    token = uuid.uuid4().hex
    if not client.set(_LOCK_KEY, token, nx=True, ex=_LOCK_TTL):
        return False
    try:
        _run_alembic_upgrade()
    finally:
        _release_own_lock(client, token)
    return True


def main(client: redis.Redis | None = None) -> None:
    client = client or redis.Redis.from_url(settings.redis_url)
    _wait_redis(client)
    while not _try_migrate_once(client):
        # 没抢到：等持锁者释放（或锁 TTL 过期）后回到循环重抢、自己再跑一遍迁移兜底
        while client.get(_LOCK_KEY) is not None:
            time.sleep(1)


if __name__ == "__main__":
    main()
