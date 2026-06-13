import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.redis_url.startswith("redis://")
    assert s.minio_bucket_sources == "sources"
    assert s.jwt_expire_min == 720
    assert "+asyncpg" in s.database_url


def test_prod_rejects_weak_default_secrets():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="prod")  # 默认 jwt_secret/minio 凭据弱 → 拒绝


def test_prod_accepts_strong_secrets():
    s = Settings(
        _env_file=None,
        app_env="prod",
        jwt_secret="x" * 40,
        minio_access_key="realkey",
        minio_secret_key="realsecret",
    )
    assert s.app_env == "prod"


def test_dev_keeps_defaults_usable():
    s = Settings(_env_file=None)  # 默认 app_env=dev，弱默认不报错（本地/测试可用）
    assert s.jwt_secret == "change-me-in-prod"
