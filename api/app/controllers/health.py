from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """存活探针（liveness）：进程在跑即 ok。"""
    return {"status": "ok"}


async def _check_db() -> bool:
    try:
        async with SessionLocal() as s:
            await s.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — 探针只关心通/不通
        return False


async def _check_redis() -> bool:
    try:
        from redis.asyncio import from_url

        client = from_url(settings.redis_url)
        try:
            await client.ping()
        finally:
            await client.aclose()
        return True
    except Exception:  # noqa: BLE001
        return False


async def _check_minio() -> bool:
    try:
        from app.controllers.sources import get_storage

        storage = get_storage()
        storage._client.bucket_exists(storage.bucket)
        return True
    except Exception:  # noqa: BLE001
        return False


@router.get("/readyz")
async def readyz(response: Response) -> dict:
    """就绪探针（readiness）：探 DB/Redis/MinIO，任一不通返回 503，供滚动发布/负载均衡摘流。"""
    checks = {
        "db": await _check_db(),
        "redis": await _check_redis(),
        "minio": await _check_minio(),
    }
    ready = all(checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"ready": ready, "checks": checks}
