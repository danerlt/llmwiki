import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = logging.getLogger("app.config")
# 仅这些显式环境允许使用弱默认凭据；其它一切值（含 prod/staging/拼写错误/漏设）按生产严格处理
_DEV_ENVS = {"dev", "test", "local"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://llmwiki:llmwiki@postgres:5432/llmwiki"
    redis_url: str = "redis://redis:6379/0"
    arq_max_tries: int = 3
    arq_job_timeout: int = 900
    max_upload_bytes: int = 50 * 1024 * 1024  # 单文件上限，与 nginx client_max_body_size 对齐
    rate_limit_per_min: int = 0  # 每 IP 每分钟请求上限，<=0 关闭（生产按需开启）

    jwt_secret: str = "change-me-in-prod"
    jwt_expire_min: int = 480  # 8h，缩短被盗令牌的有效窗口（配合 token_version 吊销）

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
    app_env: str = "dev"  # 仅 dev/test/local 允许弱默认凭据，其它环境强制拒绝
    cors_origins: str = ""  # 逗号分隔的允许跨域来源；留空回退到 [app_url]

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip():
            return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return [self.app_url]

    @model_validator(mode="after")
    def _enforce_secret_strength(self) -> "Settings":
        """弱默认凭据：非 dev/test/local 环境一律拒绝启动；dev 类环境放行但显式告警。

        安全前提不系于一个默认关闭的开关——除显式白名单外的任何 APP_ENV 值
        （prod、staging、漏设导致的异常值、拼写错误）都按生产严格处理。
        """
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
            if self.app_env not in _DEV_ENVS:
                raise ValueError(
                    f"APP_ENV={self.app_env!r} 下检测到弱默认凭据，拒绝启动："
                    f"{', '.join(weak)}（仅 dev/test/local 允许弱默认，请注入强随机值）"
                )
            _logger.warning(
                "正在使用弱默认凭据 %s（APP_ENV=%s）。真实部署务必注入强随机值并设置 APP_ENV=prod。",
                ", ".join(weak),
                self.app_env,
            )
        return self


settings = Settings()
