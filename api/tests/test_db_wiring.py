from app.db.base import Base
from app.db.session import SessionLocal, engine


def test_db_objects_wired():
    assert Base.metadata is not None
    assert engine.url.get_backend_name() == "postgresql"
    assert engine.url.get_driver_name() == "asyncpg"
    session = SessionLocal()
    assert session is not None
