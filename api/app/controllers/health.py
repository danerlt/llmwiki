from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text

from app.common.api_response import api_response
from app.common.response import Response as ApiResponse
from app.core import metrics
from app.core.config import settings
from app.core.deps import require_admin
from app.db.session import SessionLocal, engine
from app.schemas.health import PoolStats

router = APIRouter(tags=["health"])


@router.get(
    "/admin/db-pool",
    response_model=ApiResponse[PoolStats],
    dependencies=[Depends(require_admin)],
)
@api_response
async def db_pool_stats() -> PoolStats:
    """连接池监控（admin）：池大小 / 已签回 / 已签出 / 溢出，排查连接泄漏或打满。"""
    pool = engine.sync_engine.pool
    return PoolStats(
        size=pool.size(),
        checked_in=pool.checkedin(),
        checked_out=pool.checkedout(),
        overflow=pool.overflow(),
    )


@router.get("/health")
async def health() -> dict[str, str]:
    """存活探针（liveness）：进程在跑即 ok。"""
    return {"status": "ok"}


@router.get("/metrics")
async def metrics_endpoint() -> Response:
    """Prometheus 抓取端点（进程内聚合的请求量与延迟）。"""
    return Response(content=metrics.render(), media_type="text/plain; version=0.0.4; charset=utf-8")


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
