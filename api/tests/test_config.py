from app.core.config import Settings


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.redis_url.startswith("redis://")
    assert s.minio_bucket_sources == "sources"
    assert s.jwt_expire_min == 720
    assert "+asyncpg" in s.database_url
