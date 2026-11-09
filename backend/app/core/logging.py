"""Cấu hình logging cho backend.

Mặc định giữ format text hiện tại. Đặt ``LOG_FORMAT=json`` để xuất mỗi bản ghi
thành một dòng JSON, thuận tiện cho thu thập log tập trung. ``LOG_LEVEL`` nhận
các mức chuẩn của :mod:`logging` (mặc định ``INFO``).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_HANDLER_MARKER = "_eyelearning_handler"


class JsonFormatter(logging.Formatter):
    """Format mỗi ``LogRecord`` thành một dòng JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Cấu hình root logger theo ``LOG_FORMAT``/``LOG_LEVEL``.

    Idempotent: gọi nhiều lần không nhân đôi handler; lần gọi sau chỉ cập nhật
    level/format theo biến môi trường hiện tại.
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    log_format = os.getenv("LOG_FORMAT", "text").strip().lower()

    root = logging.getLogger()
    root.setLevel(level)

    handler = next(
        (h for h in root.handlers if getattr(h, _HANDLER_MARKER, False)),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler()
        setattr(handler, _HANDLER_MARKER, True)
        root.addHandler(handler)

    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(TEXT_FORMAT))
