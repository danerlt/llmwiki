"""启动时数据库迁移：用 Redis 分布式锁保证多副本(api/worker)只有一个执行
`alembic upgrade head`，避免并发迁移竞争；未抢到锁的副本轮询等持锁者迁移完成后再继续启动。

容器 command 用法（docker-compose）：
    python -m app.db.migrate_with_lock && uvicorn app.main:app ...
"""
import time

import redis
from alembic import command
from alembic.config import Config

from app.core.config import settings

_LOCK_KEY = "llmwiki:migrate:lock"
_LOCK_TTL = 300  # 秒；迁移应远快于此，TTL 防持锁进程崩溃后死锁


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


def main(client: redis.Redis | None = None) -> None:
    client = client or redis.Redis.from_url(settings.redis_url)
    _wait_redis(client)
    # 抢到锁的副本跑迁移；没抢到的轮询等它释放（迁移完成）后再继续
    if client.set(_LOCK_KEY, "migrating", nx=True, ex=_LOCK_TTL):
        try:
            _run_alembic_upgrade()
        finally:
            client.delete(_LOCK_KEY)
    else:
        while client.get(_LOCK_KEY) is not None:
            time.sleep(1)


if __name__ == "__main__":
    main()
