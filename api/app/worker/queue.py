from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings

# 进程内单例 arq 连接池：避免每次入队都新建/关闭连接（旧实现每次 create_pool+close，
# 既慢又触发 arq 的 close() deprecation 警告）。
_pool: ArqRedis | None = None


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool


async def enqueue_ingest(source_id: str) -> str:
    """入队 ingest_source，返回 arq job_id。"""
    pool = await get_pool()
    job = await pool.enqueue_job("ingest_source", source_id)
    return job.job_id
