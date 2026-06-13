from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings


async def enqueue_ingest(source_id: str) -> str:
    """入队 ingest_source，返回 arq job_id。"""
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        job = await pool.enqueue_job("ingest_source", source_id)
        return job.job_id
    finally:
        await pool.close()
