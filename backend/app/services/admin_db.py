"""Dịch vụ truy vấn CSDL chỉ đọc cho admin.

Mọi truy vấn đi qua một engine riêng với:
- transaction read-only;
- statement/lock timeout;
- role DB hạn chế (khuyến nghị `admin_reader`);
- giới hạn số dòng, kích thước cell và tổng response.

Lớp validate SQL chỉ là bổ sung. Lớp bảo vệ chính là transaction read-only
cộng với quyền hạn của role DB.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.schemas.admin_db import (
    AdminDbColumnOut,
    AdminDbFilterIn,
    AdminDbQueryOut,
    AdminDbResultColumnOut,
    AdminDbSchemaOut,
    AdminDbTableOut,
    AdminDbTableRowsOut,
)
from app.services.admin_db_serialize import (
    _cap_response_size,
    _result_columns,
    _serialize_value,
)
from app.services.admin_db_validation import (
    _build_filter_clause,
    _build_order_clause,
    _find_table,
    _quote_ident,
    validate_sql,
)

logger = logging.getLogger("app.admin_db")

# ---------------------------------------------------------------------------
# Engine riêng, read-only
# ---------------------------------------------------------------------------

_admin_engine: AsyncEngine | None = None


def _normalize_async_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    return url


def get_admin_db_url() -> str:
    configured = settings.admin_db_url.strip()
    if configured:
        return _normalize_async_url(configured)
    if settings.debug:
        # Dev/test: dùng chung DSN chính nhưng mọi transaction vẫn read-only.
        return _normalize_async_url(settings.database_url)
    raise RuntimeError(
        "Tính năng truy vấn CSDL chưa được cấu hình. "
        "Đặt ADMIN_DB_URL trỏ tới role chỉ đọc (admin_reader)."
    )


def get_admin_engine() -> AsyncEngine:
    global _admin_engine
    if _admin_engine is None:
        _admin_engine = create_async_engine(
            get_admin_db_url(),
            poolclass=NullPool,
            pool_pre_ping=True,
            connect_args={
                "server_settings": {
                    "application_name": "eyelearning-admin-db",
                    "default_transaction_read_only": "on",
                    "statement_timeout": str(settings.admin_db_statement_timeout_ms),
                    "lock_timeout": str(settings.admin_db_lock_timeout_ms),
                    "idle_in_transaction_session_timeout": str(
                        settings.admin_db_idle_in_transaction_timeout_ms
                    ),
                }
            },
        )
    return _admin_engine


# ---------------------------------------------------------------------------
# Schema introspection
# ---------------------------------------------------------------------------

_SCHEMA_SQL = text(
    """
    SELECT
        n.nspname AS schema_name,
        c.relname AS table_name,
        CASE c.relkind
            WHEN 'r' THEN 'table'
            WHEN 'p' THEN 'partitioned_table'
            WHEN 'v' THEN 'view'
            WHEN 'm' THEN 'materialized_view'
            WHEN 'f' THEN 'foreign_table'
            ELSE 'table'
        END AS kind,
        CASE
            WHEN c.relkind IN ('r', 'p')
            THEN GREATEST(c.reltuples, 0)::bigint
            ELSE NULL
        END AS row_estimate,
        a.attname AS column_name,
        format_type(a.atttypid, a.atttypmod) AS data_type,
        NOT a.attnotnull AS nullable,
        COALESCE(pk.is_primary, false) AS primary_key,
        pg_get_expr(ad.adbin, ad.adrelid) AS default_value
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a
      ON a.attrelid = c.oid
     AND a.attnum > 0
     AND NOT a.attisdropped
    LEFT JOIN pg_attrdef ad
      ON ad.adrelid = c.oid
     AND ad.adnum = a.attnum
    LEFT JOIN LATERAL (
        SELECT true AS is_primary
        FROM pg_index i
        WHERE i.indrelid = c.oid
          AND i.indisprimary
          AND a.attnum = ANY(i.indkey::smallint[])
        LIMIT 1
    ) pk ON true
    WHERE n.nspname = 'public'
      AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
      AND NOT c.relispartition
      AND c.relname <> 'schema_migrations'
      AND (
          has_table_privilege(c.oid, 'SELECT')
          OR has_any_column_privilege(c.oid, 'SELECT')
      )
      AND has_column_privilege(c.oid, a.attnum, 'SELECT')
    ORDER BY
        CASE c.relkind
            WHEN 'r' THEN 0
            WHEN 'p' THEN 0
            WHEN 'v' THEN 1
            WHEN 'm' THEN 1
            ELSE 2
        END,
        c.relname,
        a.attnum
    """
)

_schema_cache: tuple[float, AdminDbSchemaOut] | None = None


def _build_schema(rows: list[Any]) -> list[AdminDbTableOut]:
    tables: dict[tuple[str, str], AdminDbTableOut] = {}
    for row in rows:
        key = (row.schema_name, row.table_name)
        table = tables.get(key)
        if table is None:
            table = AdminDbTableOut(
                schema_name=row.schema_name,
                name=row.table_name,
                kind=row.kind,
                row_estimate=(int(row.row_estimate) if row.row_estimate is not None else None),
                columns=[],
            )
            tables[key] = table
        table.columns.append(
            AdminDbColumnOut(
                name=row.column_name,
                type=row.data_type,
                nullable=bool(row.nullable),
                primary_key=bool(row.primary_key),
                default=row.default_value,
            )
        )
    return list(tables.values())


async def get_schema(force_refresh: bool = False) -> AdminDbSchemaOut:
    global _schema_cache
    now = time.monotonic()
    if (
        not force_refresh
        and _schema_cache is not None
        and settings.admin_db_schema_cache_seconds > 0
        and now - _schema_cache[0] < settings.admin_db_schema_cache_seconds
    ):
        return _schema_cache[1]

    engine = get_admin_engine()
    async with engine.connect() as conn:
        result = await conn.execute(_SCHEMA_SQL)
        rows = result.all()

    schema = AdminDbSchemaOut(
        tables=_build_schema(rows),
        generated_at=datetime.now(timezone.utc),
    )
    _schema_cache = (now, schema)
    return schema


# ---------------------------------------------------------------------------
# Lỗi & audit log
# ---------------------------------------------------------------------------

_FRIENDLY_ERRORS = {
    "42601": "Câu lệnh SQL có lỗi cú pháp.",
    "42P01": "Bảng không tồn tại hoặc bạn không có quyền đọc.",
    "42703": "Cột không tồn tại trong bảng.",
    "42883": "Hàm không tồn tại.",
    "42501": "Bạn không có quyền đọc bảng/cột này.",
    "25006": "Chế độ chỉ đọc không cho phép thay đổi dữ liệu.",
    "57014": "Truy vấn vượt quá thời gian cho phép.",
    "22P02": "Giá trị không đúng định dạng.",
    "22012": "Không thể chia cho 0.",
    "22003": "Giá trị số vượt quá phạm vi.",
    "23505": "Dữ liệu bị trùng khóa.",
    "23503": "Dữ liệu tham chiếu không hợp lệ.",
    "40001": "Truy vấn bị xung đột, vui lòng thử lại.",
    "40P01": "Phát hiện deadlock, vui lòng thử lại.",
    "55P03": "Không thể khóa dữ liệu, vui lòng thử lại.",
    "53300": "CSDL đang quá tải kết nối.",
    "08006": "Mất kết nối CSDL.",
    "08003": "Kết nối CSDL không tồn tại.",
    "28P01": "Sai thông tin đăng nhập CSDL.",
    "3D000": "CSDL không tồn tại.",
}

_UNAVAILABLE_SQLSTATES = {
    "53300",
    "57P01",
    "57P02",
    "57P03",
    "28P01",
    "28000",
    "3D000",
}


def _query_error(exc: DBAPIError) -> HTTPException:
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    message = getattr(orig, "message", None) or str(orig) or str(exc)
    detail = getattr(orig, "detail", None)
    hint = getattr(orig, "hint", None)
    position = getattr(orig, "position", None)

    friendly = _FRIENDLY_ERRORS.get(
        sqlstate or "",
        "Không chạy được truy vấn. Kiểm tra cú pháp và quyền truy cập.",
    )
    if sqlstate == "57014":
        seconds = max(1, settings.admin_db_statement_timeout_ms // 1000)
        friendly = f"Truy vấn vượt quá thời gian cho phép ({seconds} giây)."

    unavailable = bool(
        sqlstate and (sqlstate.startswith("08") or sqlstate in _UNAVAILABLE_SQLSTATES)
    )
    return HTTPException(
        status_code=(
            status.HTTP_503_SERVICE_UNAVAILABLE if unavailable else status.HTTP_400_BAD_REQUEST
        ),
        detail={
            "code": sqlstate or "SQL_ERROR",
            "message": friendly,
            "detail": detail or message,
            "hint": hint,
            "position": position,
        },
    )


def _error_code(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code")
        if isinstance(code, str):
            return code
    return "SQL_ERROR"


def _log_query(
    user_id: str,
    sql: str,
    duration_ms: int,
    row_count: int,
    truncated: bool,
    error_code: str | None,
) -> None:
    safe_sql = " ".join(sql.split())[:500]
    logger.info(
        "admin_db_query user_id=%s duration_ms=%s rows=%s truncated=%s error=%s sql=%s",
        user_id,
        duration_ms,
        row_count,
        truncated,
        error_code or "-",
        safe_sql,
    )


@asynccontextmanager
async def _read_only_connection(
    *, user_id: str, label: str, unexpected_detail: str
) -> AsyncIterator[tuple[AsyncConnection, float]]:
    """Mở transaction read-only và map lỗi DB/không mong đợi thống nhất."""
    started = time.perf_counter()
    try:
        engine = get_admin_engine()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    try:
        async with engine.connect() as conn:
            async with conn.begin():
                await conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                yield conn, started
    except HTTPException:
        raise
    except DBAPIError as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        error = _query_error(exc)
        _log_query(user_id, label, duration_ms, 0, False, _error_code(error))
        raise error from exc
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.perf_counter() - started) * 1000)
        _log_query(user_id, label, duration_ms, 0, False, "UNEXPECTED")
        logger.exception("admin_db_unexpected user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=unexpected_detail,
        ) from exc


# ---------------------------------------------------------------------------
# Chạy truy vấn
# ---------------------------------------------------------------------------


async def run_query(sql: str, max_rows: int, *, user_id: str) -> AdminDbQueryOut:
    normalized = validate_sql(sql)
    limit = max(1, min(max_rows, settings.admin_db_max_rows))
    wrapped = f"SELECT * FROM (\n{normalized}\n) AS _admin_query LIMIT {limit + 1}"

    async with _read_only_connection(
        user_id=user_id,
        label=normalized,
        unexpected_detail="Không chạy được truy vấn.",
    ) as (conn, started):
        result = await conn.exec_driver_sql(wrapped)
        raw_rows = result.fetchmany(limit + 1)
        description = result.cursor.description if result.cursor is not None else None
        columns = await _result_columns(conn, result, description)
        rows = [
            [_serialize_value(value) for value in row] for row in raw_rows[:limit]
        ]
        truncated = len(raw_rows) > limit

    duration_ms = int((time.perf_counter() - started) * 1000)
    rows, truncated = _cap_response_size(rows, truncated)
    _log_query(
        user_id,
        normalized,
        duration_ms,
        len(rows),
        truncated,
        None,
    )
    return AdminDbQueryOut(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        duration_ms=duration_ms,
        limit=limit,
    )


async def browse_table(
    table_name: str,
    *,
    schema_name: str,
    columns: list[str],
    limit: int,
    offset: int,
    order_by: str | None,
    order_dir: str,
    filters: list[AdminDbFilterIn],
    user_id: str,
) -> AdminDbTableRowsOut:
    """Duyệt bảng/view bằng tham số có cấu trúc.

    Table/column/order/filter column được validate với schema cache (đã lọc
    theo quyền của role DB). Identifier được quote; value được bind.
    """
    schema = await get_schema()
    table = _find_table(schema, schema_name, table_name)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bảng không tồn tại hoặc bạn không có quyền đọc.",
        )

    allowed_columns = {column.name: column for column in table.columns}
    if not allowed_columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bảng không có cột nào bạn được phép đọc.",
        )

    if columns:
        selected: list[str] = []
        for name in columns:
            if name not in allowed_columns:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(f"Cột {name} không tồn tại hoặc không có quyền đọc."),
                )
            if name not in selected:
                selected.append(name)
    else:
        selected = list(allowed_columns)

    if not selected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng chọn ít nhất một cột.",
        )

    if order_by and order_by not in allowed_columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Cột sắp xếp {order_by} không tồn tại hoặc không có quyền đọc."),
        )

    params: dict[str, Any] = {}
    where_parts = _build_filter_clause(filters, allowed_columns, params)
    select_clause = ", ".join(_quote_ident(name) for name in selected)
    table_ref = f"{_quote_ident(schema_name)}.{_quote_ident(table_name)}"
    sql = f"SELECT {select_clause} FROM {table_ref}"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    order_clause = _build_order_clause(table, order_by, order_dir)
    if order_clause:
        sql += " " + order_clause
    sql += " LIMIT :limit OFFSET :offset"
    params["limit"] = limit + 1
    params["offset"] = offset

    label = f"TABLE {schema_name}.{table_name}"
    async with _read_only_connection(
        user_id=user_id,
        label=label,
        unexpected_detail="Không tải được dữ liệu bảng.",
    ) as (conn, started):
        result = await conn.execute(text(sql), params)
        raw_rows = result.fetchall()
        # Dùng type từ schema (đã validate) thay vì cursor description để ổn
        # định với cả query có bind param.
        result_columns = [
            AdminDbResultColumnOut(
                name=name,
                type=allowed_columns[name].type,
            )
            for name in selected
        ]
        rows = [
            [_serialize_value(value) for value in row] for row in raw_rows[:limit]
        ]
        has_more = len(raw_rows) > limit

    duration_ms = int((time.perf_counter() - started) * 1000)
    rows, capped = _cap_response_size(rows, has_more)
    has_more = has_more or capped
    _log_query(
        user_id,
        f"TABLE {schema_name}.{table_name}",
        duration_ms,
        len(rows),
        has_more,
        None,
    )
    return AdminDbTableRowsOut(
        columns=result_columns,
        rows=rows,
        row_count=len(rows),
        limit=limit,
        offset=offset,
        has_more=has_more,
        duration_ms=duration_ms,
    )
