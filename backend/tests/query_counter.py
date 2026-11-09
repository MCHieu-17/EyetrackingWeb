"""Đếm số câu SQL phát ra bởi một engine — dùng cho test hiệu năng (P4).

Helper này chỉ lắng nghe sự kiện của SQLAlchemy, không đổi hành vi query.
Hỗ trợ cả ``Engine`` đồng bộ và ``AsyncEngine`` (dùng ``sync_engine`` bên trong).

Ví dụ::

    from tests.query_counter import count_queries

    async with count_queries(engine) as counter:
        await some_service(db)
    assert counter.count <= 5
    print(counter.statements)
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass
class QueryCounter:
    """Kết quả đếm: danh sách câu SQL theo đúng thứ tự phát ra."""

    statements: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.statements)

    def reset(self) -> None:
        self.statements.clear()


def _sync_engine(engine: Engine | AsyncEngine) -> Engine:
    return engine.sync_engine if isinstance(engine, AsyncEngine) else engine


@contextmanager
def count_queries(engine: Engine | AsyncEngine) -> Iterator[QueryCounter]:
    """Đếm mọi câu SQL chạy qua ``engine`` trong khối ``with``."""

    counter = QueryCounter()
    target = _sync_engine(engine)

    def before_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        counter.statements.append(statement)

    event.listen(target, "before_cursor_execute", before_cursor_execute)
    try:
        yield counter
    finally:
        event.remove(target, "before_cursor_execute", before_cursor_execute)
