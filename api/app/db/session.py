from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,  # 取连接前 ping，跳过被 DB/代理静默断开的死连接
    pool_recycle=1800,  # 30min 回收，早于常见 DB/代理空闲超时，避免“server closed connection”
    pool_size=10,
    max_overflow=20,
    connect_args={"command_timeout": 30},  # asyncpg 单条 SQL 超时，防慢查询占满连接
    future=True,
)
# expire_on_commit=False：commit 后不过期已加载对象（配套 service 层显式 refresh 规范）
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
