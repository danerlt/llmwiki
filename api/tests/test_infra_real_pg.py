"""阶段2 测试基座：证明测试跑在真实 PostgreSQL（而非内存 SQLite）上。

这两个测试是 phase 2 的红线——只有当 conftest 真正连到 PG 且迁移链建好
pg_trgm 扩展时才会通过；在内存 SQLite 上必然失败。
"""
from sqlalchemy import text


async def test_session_runs_on_real_postgresql(session):
    # 内存 SQLite 上 dialect.name == "sqlite"，真实 PG 上为 "postgresql"
    assert session.bind.dialect.name == "postgresql"


async def test_pg_trgm_extension_present(session):
    # pg_trgm 是关键词检索 GIN 索引(ix_wiki_*_trgm)的依赖；迁移链应已建好它
    row = await session.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'pg_trgm'")
    )
    assert row.scalar_one_or_none() == "pg_trgm"
