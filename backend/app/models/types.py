"""Custom SQLAlchemy types cho schema hiện hành.

`Vector` ánh xạ cột pgvector trong model/metadata; query vector thật do service
embedding/chatbot dùng raw SQL hoặc pgvector.
"""

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dim: int = 1024):
        self.dim = dim

    def get_col_spec(self, **kw) -> str:  # noqa: ARG002
        return f"vector({self.dim})"
