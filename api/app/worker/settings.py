from arq.connections import RedisSettings

from app.core.config import settings


class WorkerSettings:
    functions: list = []
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = settings.arq_max_tries
    job_timeout = settings.arq_job_timeout
