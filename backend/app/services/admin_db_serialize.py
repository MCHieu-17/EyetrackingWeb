"""Chuẩn hoá dữ liệu PostgreSQL trả về cho admin API.

Giữ toàn bộ giá trị lớn dưới dạng string an toàn cho JavaScript và áp giới hạn
cell/response.
"""

from __future__ import annotations

import ipaddress
import json
import math
import uuid
from datetime import date, datetime, timedelta
from datetime import time as dt_time
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.schemas.admin_db import AdminDbResultColumnOut

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
