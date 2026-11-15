"""Validation SQL và structured-filter cho admin database.

Tách khỏi execution để phần bảo mật SQL có ranh giới rõ và test độc lập.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.admin_db import (
    AdminDbColumnOut,
    AdminDbFilterIn,
    AdminDbSchemaOut,
    AdminDbTableOut,
)

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
