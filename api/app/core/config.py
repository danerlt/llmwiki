from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://llmwiki:llmwiki@postgres:5432/llmwiki"
    redis_url: str = "redis://redis:6379/0"
    arq_max_tries: int = 3
    arq_job_timeout: int = 900

    jwt_secret: str = "change-me-in-prod"
    jwt_expire_min: int = 720

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_sources: str = "sources"
    minio_bucket_assets: str = "assets"
    minio_secure: bool = False

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    app_url: str = "http://localhost"


settings = Settings()
