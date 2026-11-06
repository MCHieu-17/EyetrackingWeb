"""Custom SQLAlchemy types cho schema mới.

`Vector` chỉ cần cho DDL/catalog mapping ở Phase 1. Các query vector thật sẽ
dùng raw SQL hoặc pgvector ở Phase 5.
"""

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dim: int = 1024):
        self.dim = dim

    def get_col_spec(self, **kw) -> str:  # noqa: ARG002
        return f"vector({self.dim})"
