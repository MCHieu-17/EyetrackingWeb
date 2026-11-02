"""Connection pool PostgreSQL dùng chung cho retriever + ingestion.

`register_vector` được cấu hình cho MỌI connection trong pool để pgvector hoạt
động ở retriever/ingestion.
"""

import logging
import threading

from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.settings import database_url, db_pool_max, db_pool_min

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None
_lock = threading.Lock()


def _configure(conn) -> None:
    register_vector(conn)


def get_pool() -> ConnectionPool:
    """Lazy singleton pool; tạo lần đầu khi cần."""
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                _pool = ConnectionPool(
                    conninfo=database_url(),
                    min_size=db_pool_min(),
                    max_size=db_pool_max(),
                    kwargs={
                        "autocommit": True,
                        "row_factory": dict_row,
                        "prepare_threshold": 0,
                    },
                    configure=_configure,
                    check=ConnectionPool.check_connection,
                    open=True,
                )
                logger.info("Đã mở DB connection pool")
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
