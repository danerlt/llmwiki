from pydantic import BaseModel


class PoolStats(BaseModel):
    """SQLAlchemy 连接池实时状态（排查连接泄漏 / 打满）。"""

    size: int
    checked_in: int
    checked_out: int
    overflow: int
