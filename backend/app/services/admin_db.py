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

import ipaddress
import json
import logging
import math
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from datetime import time as dt_time
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
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
# Duyệt bảng (structured query, không nhận raw SQL)
# ---------------------------------------------------------------------------

_FILTER_SQL_OPERATORS = {
    "eq": "=",
    "neq": "<>",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _find_table(
    schema: AdminDbSchemaOut, schema_name: str, table_name: str
) -> AdminDbTableOut | None:
    for table in schema.tables:
        if table.schema_name == schema_name and table.name == table_name:
            return table
    return None


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_filter_clause(
    filters: list[AdminDbFilterIn],
    allowed_columns: dict[str, AdminDbColumnOut],
    params: dict[str, Any],
) -> list[str]:
    parts: list[str] = []
    for index, item in enumerate(filters):
        if item.column not in allowed_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(f"Cột {item.column} không tồn tại hoặc không có quyền đọc."),
            )
        column = _quote_ident(item.column)
        key = f"f{index}"

        if item.operator == "is_null":
            parts.append(f"{column} IS NULL")
            continue
        if item.operator == "is_not_null":
            parts.append(f"{column} IS NOT NULL")
            continue
        if item.value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vui lòng nhập giá trị cho bộ lọc {item.column}.",
            )

        if item.operator in {"contains", "starts_with", "ends_with"}:
            params[key] = _escape_like(item.value)
            cast_column = f"CAST({column} AS text)"
            if item.operator == "contains":
                parts.append(f"{cast_column} ILIKE '%' || :{key} || '%' ESCAPE '\\'")
            elif item.operator == "starts_with":
                parts.append(f"{cast_column} ILIKE :{key} || '%' ESCAPE '\\'")
            else:
                parts.append(f"{cast_column} ILIKE '%' || :{key} ESCAPE '\\'")
            continue

        params[key] = item.value
        parts.append(f"{column} {_FILTER_SQL_OPERATORS[item.operator]} :{key}")
    return parts


def _build_order_clause(table: AdminDbTableOut, order_by: str | None, order_dir: str) -> str:
    primary_keys = [column.name for column in table.columns if column.primary_key]
    if order_by:
        columns = [order_by] + [name for name in primary_keys if name != order_by]
    else:
        columns = primary_keys
    if not columns:
        return ""
    direction = "DESC" if order_dir == "desc" else "ASC"
    return "ORDER BY " + ", ".join(f"{_quote_ident(name)} {direction}" for name in columns)


# ---------------------------------------------------------------------------
# Validate SQL
# ---------------------------------------------------------------------------

_ALLOWED_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_DOLLAR_TAG = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$")
_DANGEROUS_FUNCTIONS = re.compile(
    r"\b("
    r"set_config|"
    r"pg_read_\w*|pg_ls_\w*|pg_stat_file|"
    r"lo_\w*|dblink\w*|"
    r"pg_terminate_backend|pg_cancel_backend|pg_reload_conf|"
    r"pg_rotate_logfile|pg_switch_wal|pg_create_restore_point|pg_promote|"
    r"pg_backup_\w*|pg_start_backup|pg_stop_backup|"
    r"pg_wal_replay_\w*|pg_logical_emit_message|"
    r"pg_replication_origin_\w*|"
    r"pg_create_\w*replication_slot|pg_drop_replication_slot|"
    r"pg_copy_\w*replication_slot|pg_replication_slot_advance|"
    r"pg_stat_reset\w*|"
    r"pg_advisory_\w*|pg_try_advisory_\w*|"
    r"pg_sleep\w*"
    r")\s*\(",
    re.IGNORECASE,
)


def _sanitize_sql(sql: str, *, keep_quoted_identifiers: bool) -> str:
    """Thay nội dung chuỗi/comment bằng khoảng trắng để kiểm tra keyword.

    Giữ nguyên độ dài chuỗi để có thể xác định vị trí dấu `;` cuối câu.
    Với `keep_quoted_identifiers=True`, nội dung identifier trong dấu `"` được
    giữ lại để bắt các lời gọi hàm kiểu `"set_config"(...)`.
    """
    out = list(sql)
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]

        # Line comment
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            j = i
            while j < n and sql[j] != "\n":
                out[j] = " "
                j += 1
            i = j
            continue

        # Block comment
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            j = i
            while j < n:
                if sql[j] == "*" and j + 1 < n and sql[j + 1] == "/":
                    j += 2
                    break
                out[j] = " "
                j += 1
            else:
                j = n
            for k in range(i, min(j, n)):
                out[k] = " "
            i = j
            continue

        # Single-quoted string
        if ch == "'":
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            for k in range(i, min(j, n)):
                out[k] = " "
            i = j
            continue

        # Double-quoted identifier
        if ch == '"':
            if keep_quoted_identifiers:
                out[i] = " "
                j = i + 1
                while j < n:
                    if sql[j] == '"':
                        if j + 1 < n and sql[j + 1] == '"':
                            out[j] = " "
                            out[j + 1] = " "
                            j += 2
                            continue
                        out[j] = " "
                        j += 1
                        break
                    j += 1
                i = j
            else:
                j = i + 1
                while j < n:
                    if sql[j] == '"':
                        if j + 1 < n and sql[j + 1] == '"':
                            j += 2
                            continue
                        j += 1
                        break
                    j += 1
                for k in range(i, min(j, n)):
                    out[k] = " "
                i = j
            continue

        # Dollar-quoted string
        if ch == "$":
            match = _DOLLAR_TAG.match(sql, i)
            if match:
                tag = match.group(0)
                end = sql.find(tag, i + len(tag))
                if end == -1:
                    end = n
                else:
                    end += len(tag)
                for k in range(i, min(end, n)):
                    out[k] = " "
                i = end
                continue

        i += 1
    return "".join(out)


def _has_multiple_statements(sanitized: str) -> bool:
    stripped = sanitized.rstrip()
    if stripped.endswith(";"):
        stripped = stripped[:-1]
    return ";" in stripped


def validate_sql(sql: str) -> str:
    normalized = sql.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng nhập câu lệnh SQL.",
        )
    if len(normalized) > settings.admin_db_max_sql_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Câu lệnh quá dài (tối đa {settings.admin_db_max_sql_length} ký tự)."),
        )

    sanitized = _sanitize_sql(normalized, keep_quoted_identifiers=False)
    if not _ALLOWED_START.match(sanitized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ cho phép câu lệnh SELECT hoặc WITH.",
        )
    if _has_multiple_statements(sanitized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ được chạy một câu lệnh trong mỗi lần truy vấn.",
        )

    sanitized_for_functions = _sanitize_sql(normalized, keep_quoted_identifiers=True)
    match = _DANGEROUS_FUNCTIONS.search(sanitized_for_functions)
    if match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Hàm {match.group(1)} không được phép trong chế độ chỉ đọc."),
        )

    # Bỏ dấu ; cuối câu (kể cả khi phía sau có comment) để có thể bọc query.
    stripped = sanitized.rstrip()
    if stripped.endswith(";"):
        index = len(stripped) - 1
        normalized = (normalized[:index] + normalized[index + 1 :]).rstrip()
    return normalized


# ---------------------------------------------------------------------------
# Serialize kết quả
# ---------------------------------------------------------------------------

_TYPE_OID_NAMES: dict[int, str] = {
    16: "boolean",
    17: "bytea",
    18: "character",
    19: "name",
    20: "bigint",
    21: "smallint",
    23: "integer",
    25: "text",
    26: "oid",
    114: "json",
    142: "xml",
    600: "point",
    601: "lseg",
    602: "path",
    603: "box",
    604: "polygon",
    628: "line",
    650: "cidr",
    700: "real",
    701: "double precision",
    705: "unknown",
    718: "circle",
    790: "money",
    829: "macaddr",
    869: "inet",
    1042: "character",
    1043: "character varying",
    1082: "date",
    1083: "time without time zone",
    1114: "timestamp without time zone",
    1184: "timestamp with time zone",
    1186: "interval",
    1266: "time with time zone",
    1560: "bit",
    1562: "bit varying",
    1700: "numeric",
    1790: "refcursor",
    2202: "regprocedure",
    2203: "regoper",
    2204: "regoperator",
    2205: "regclass",
    2206: "regtype",
    2950: "uuid",
    3220: "pg_lsn",
    3614: "tsvector",
    3615: "tsquery",
    3802: "jsonb",
    3904: "int4range",
    3906: "numrange",
    3908: "tsrange",
    3910: "tstzrange",
    3912: "daterange",
    3926: "int8range",
    4451: "int4multirange",
    4532: "nummultirange",
    4533: "tsmultirange",
    4534: "tstzmultirange",
    4535: "datemultirange",
    4536: "int8multirange",
}


async def _resolve_type_names(conn: Any, oids: list[int]) -> dict[int, str]:
    type_map = {oid: _TYPE_OID_NAMES[oid] for oid in oids if oid in _TYPE_OID_NAMES}
    unknown = sorted({oid for oid in oids if oid not in type_map})
    if unknown:
        rows = (
            await conn.execute(
                text(
                    "SELECT oid, format_type(oid, NULL) AS name FROM pg_type WHERE oid = ANY(:oids)"
                ),
                {"oids": unknown},
            )
        ).all()
        type_map.update({int(row.oid): row.name for row in rows})
    return type_map


def _description_name(col: Any) -> str | None:
    if hasattr(col, "name"):
        return col.name
    if isinstance(col, (tuple, list)) and col:
        return col[0]
    return None


def _description_type_code(col: Any) -> int | None:
    if hasattr(col, "type_code"):
        return col.type_code
    if isinstance(col, (tuple, list)) and len(col) > 1:
        return col[1]
    return None


async def _result_columns(conn: Any, result: Any, description: Any) -> list[AdminDbResultColumnOut]:
    if description:
        oids = [
            int(code) for col in description if (code := _description_type_code(col)) is not None
        ]
        type_map = await _resolve_type_names(conn, oids)
        columns: list[AdminDbResultColumnOut] = []
        for index, col in enumerate(description):
            type_code = _description_type_code(col)
            columns.append(
                AdminDbResultColumnOut(
                    name=_description_name(col) or f"column_{index + 1}",
                    type=(
                        type_map.get(int(type_code), f"oid:{type_code}")
                        if type_code is not None
                        else "unknown"
                    ),
                )
            )
        return columns
    return [AdminDbResultColumnOut(name=str(name), type="unknown") for name in result.keys()]


def _truncate_text(value: str) -> str:
    limit = settings.admin_db_max_cell_chars
    if limit <= 0 or len(value) <= limit:
        return value
    return value[:limit] + "…"


def _truncate_json(value: Any) -> Any:
    try:
        encoded = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        return _truncate_text(str(value))
    if len(encoded) <= settings.admin_db_max_cell_chars:
        return value
    return _truncate_text(encoded)


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        # JSON number của JavaScript mất precision > 2^53; trả string cho bigint
        # lớn để admin vẫn thấy đúng giá trị.
        if abs(value) > 2**53 - 1:
            return str(value)
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return str(value)
        return value
    if isinstance(value, str):
        return _truncate_text(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, dt_time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<binary {len(value)} bytes>"
    if isinstance(
        value,
        (
            ipaddress.IPv4Address,
            ipaddress.IPv6Address,
            ipaddress.IPv4Network,
            ipaddress.IPv6Network,
            ipaddress.IPv4Interface,
            ipaddress.IPv6Interface,
        ),
    ):
        return str(value)
    if isinstance(value, dict):
        return _truncate_json(value)
    if isinstance(value, (list, tuple)):
        return _truncate_json(list(value))
    if hasattr(value, "tolist"):
        try:
            return _serialize_value(value.tolist())
        except Exception:  # noqa: BLE001
            pass
    return _truncate_text(str(value))


def _cap_response_size(rows: list[list[Any]], truncated: bool) -> tuple[list[list[Any]], bool]:
    max_bytes = settings.admin_db_max_response_bytes
    if max_bytes <= 0:
        return rows, truncated
    kept: list[list[Any]] = []
    total = 0
    for row in rows:
        try:
            size = len(json.dumps(row, ensure_ascii=False, default=str).encode("utf-8"))
        except Exception:  # noqa: BLE001
            size = len(str(row).encode("utf-8"))
        if total + size > max_bytes:
            return kept, True
        kept.append(row)
        total += size
    return kept, truncated


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


# ---------------------------------------------------------------------------
# Chạy truy vấn
# ---------------------------------------------------------------------------


async def run_query(sql: str, max_rows: int, *, user_id: str) -> AdminDbQueryOut:
    normalized = validate_sql(sql)
    limit = max(1, min(max_rows, settings.admin_db_max_rows))
    wrapped = f"SELECT * FROM (\n{normalized}\n) AS _admin_query LIMIT {limit + 1}"
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
                result = await conn.exec_driver_sql(wrapped)
                raw_rows = result.fetchmany(limit + 1)
                description = result.cursor.description if result.cursor is not None else None
                columns = await _result_columns(conn, result, description)
                rows = [[_serialize_value(value) for value in row] for row in raw_rows[:limit]]
                truncated = len(raw_rows) > limit
    except HTTPException:
        raise
    except DBAPIError as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        error = _query_error(exc)
        _log_query(
            user_id,
            normalized,
            duration_ms,
            0,
            False,
            _error_code(error),
        )
        raise error from exc
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.perf_counter() - started) * 1000)
        _log_query(user_id, normalized, duration_ms, 0, False, "UNEXPECTED")
        logger.exception("admin_db_query_unexpected user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không chạy được truy vấn.",
        ) from exc

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
                result = await conn.execute(text(sql), params)
                raw_rows = result.fetchall()
                # Dùng type từ schema (đã validate) thay vì cursor description
                # để ổn định với cả query có bind param.
                result_columns = [
                    AdminDbResultColumnOut(
                        name=name,
                        type=allowed_columns[name].type,
                    )
                    for name in selected
                ]
                rows = [[_serialize_value(value) for value in row] for row in raw_rows[:limit]]
                has_more = len(raw_rows) > limit
    except HTTPException:
        raise
    except DBAPIError as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        error = _query_error(exc)
        _log_query(
            user_id,
            f"TABLE {schema_name}.{table_name}",
            duration_ms,
            0,
            False,
            _error_code(error),
        )
        raise error from exc
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.perf_counter() - started) * 1000)
        _log_query(
            user_id,
            f"TABLE {schema_name}.{table_name}",
            duration_ms,
            0,
            False,
            "UNEXPECTED",
        )
        logger.exception("admin_db_browse_unexpected user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không tải được dữ liệu bảng.",
        ) from exc

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
