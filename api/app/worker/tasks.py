import uuid

from app.core.config import settings
from app.db.session import SessionLocal
from app.integrations.llm import LLMClient
from app.integrations.storage import MinioStorage
from app.services import ingest_service


async def ingest_source(ctx: dict, source_id: str) -> None:
    llm = LLMClient(
        base_url=settings.llm_base_url, api_key=settings.llm_api_key, model=settings.llm_model
    )
    storage = MinioStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket_sources,
        secure=settings.minio_secure,
    )
    async with SessionLocal() as session:
        await ingest_service.ingest_source(
            session, uuid.UUID(source_id), llm=llm, storage=storage
        )
        await session.commit()
