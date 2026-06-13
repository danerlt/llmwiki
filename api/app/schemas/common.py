from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Paginated(BaseModel, Generic[T]):
    """统一分页响应：items 当前页数据，total 总数，limit/offset 本次窗口。"""

    items: list[T]
    total: int
    limit: int
    offset: int
