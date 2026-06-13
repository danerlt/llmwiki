from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://llmwiki:llmwiki@postgres:5432/llmwiki"
    redis_url: str = "redis://redis:6379/0"
    arq_max_tries: int = 3
    arq_job_timeout: int = 900
    max_upload_bytes: int = 50 * 1024 * 1024  # 单文件上限，与 nginx client_max_body_size 对齐

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
    app_env: str = "dev"  # 设为 prod 时强制拒绝弱默认凭据

    @model_validator(mode="after")
    def _enforce_prod_secrets(self) -> "Settings":
        """生产环境(APP_ENV=prod)下，弱默认凭据快速失败而非静默回退。"""
        if self.app_env == "prod":
            weak: list[str] = []
            if (
                not self.jwt_secret
                or self.jwt_secret == "change-me-in-prod"
                or len(self.jwt_secret) < 32
            ):
                weak.append("JWT_SECRET")
            if self.minio_access_key == "minioadmin" or self.minio_secret_key == "minioadmin":
                weak.append("MINIO_ACCESS_KEY/SECRET_KEY")
            if weak:
                raise ValueError(
                    f"APP_ENV=prod 下检测到弱默认凭据，拒绝启动：{', '.join(weak)}（请注入强随机值）"
                )
        return self


settings = Settings()
