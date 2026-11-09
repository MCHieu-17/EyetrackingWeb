"""Analysis runs: run-scoped AOI hits + presentation metrics + streaming export.

Mỗi presentation được phân tích theo từng scope:
  * slide  — bộ vùng gắn với slide version đã dùng lúc học;
  * ui     — bộ vùng giao diện đã dùng trong layout snapshot.

Mẫu gaze không rơi vào vùng lá nào được gán `no_label`.
"""

from __future__ import annotations

from app.services import metrics
from app.services.analysis.common import NO_LABEL_CODE
from app.services.analysis.export import export_lines
from app.services.analysis.rebuild import rebuild_course
from app.services.analysis.runs import (
    execute_pending_runs,
    execute_run,
    get_run_result,
)

__all__ = [
    "NO_LABEL_CODE",
    "execute_pending_runs",
    "execute_run",
    "export_lines",
    "get_run_result",
    "metrics",
    "rebuild_course",
]
