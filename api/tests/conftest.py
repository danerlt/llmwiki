"""测试基座：真实 PostgreSQL + savepoint 事务隔离。

必须在任何 app 导入之前把 DATABASE_URL 指向测试库——settings 在模块加载即
实例化，alembic env.py 与 app 引擎都读 settings.database_url。
"""
import os

TEST_DATABASE_URL = os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://llmwiki:llmwiki@localhost:15433/llmwiki_test",
)
# 让 settings / alembic / app 引擎全部指向测试库与测试环境
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("REDIS_URL", "redis://localhost:16380/0")
os.environ.setdefault("APP_ENV", "test")

import logging  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

import app.models  # noqa: F401,E402  # 触发模型注册


@pytest.fixture(scope="session")
def _engine():
    """会话级：用 alembic 迁移链在真实 PG 上建好 schema（含 pg_trgm），再造 async 引擎。

    NullPool 让每个测试各开一条 asyncpg 连接（在各自的 event loop 上），
    规避 pytest-asyncio 函数级 loop 与会话级连接池的跨 loop 冲突。
    """
    cfg = Config("alembic.ini")  # env.py 用 settings.database_url（已指向测试库）
    command.upgrade(cfg, "head")
    # alembic env.py 的 fileConfig 默认 disable_existing_loggers=True，会静默掉
    # app.config/app.access 等既有 logger，导致 caplog 捕获不到——升级后恢复。
    for _lg in logging.Logger.manager.loggerDict.values():
        if isinstance(_lg, logging.Logger):
            _lg.disabled = False
    return create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)


@pytest_asyncio.fixture
async def session(_engine):
    """函数级会话：外层事务 + savepoint 隔离；测试结束回滚，用例间互不污染。

    join_transaction_mode='create_savepoint' 使业务代码内的 session.commit() 落在
    savepoint 上而非提交外层事务，从而外层 rollback 能丢弃测试期全部改动。
    """
    async with _engine.connect() as conn:
        trans = await conn.begin()
        s = AsyncSession(
            bind=conn,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield s
        finally:
            await s.close()
            await trans.rollback()


@pytest_asyncio.fixture
async def client(session):
    from app.db.session import get_db
    from app.main import app

    async def _override():
        yield session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
