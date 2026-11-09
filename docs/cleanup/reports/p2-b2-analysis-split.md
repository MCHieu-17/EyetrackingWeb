# P2-B2 — Split `services/analysis.py` thành package

## Summary

- Tách `backend/app/services/analysis.py` (1.145 dòng) thành package
  `backend/app/services/analysis/` gồm 7 module.
- Không đổi logic, SQL, response shape hay function signature. Toàn bộ 14
  function được so sánh AST với bản gốc và giống hệt từng byte.
- Public API giữ nguyên qua `__init__.py` re-export:
  `execute_run`, `get_run_result`, `rebuild_course`, `execute_pending_runs`,
  `export_lines`, `NO_LABEL_CODE` (và module `metrics` vốn importable trước đây).
- `from app.services import analysis` và
  `from app.services.analysis import execute_pending_runs` đều hoạt động;
  routes (`analytics.py`, `aoi.py`) và `worker.py` không cần sửa.

## Package layout

| Module | Nội dung | LOC |
|---|---|---|
| `analysis/__init__.py` | Docstring gốc + re-export public API (`__all__`) | 30 |
| `analysis/common.py` | `NO_LABEL_CODE`, `_now`, `_run_out`, `_watermark`, `_filters`, `_no_label_id` | 88 |
| `analysis/hits.py` | `_insert_slide_hits`, `_insert_ui_hits` | 263 |
| `analysis/runs.py` | `execute_run`, `get_run_result`, `_create_run`, `execute_pending_runs` | 187 |
| `analysis/rebuild.py` | `rebuild_course` | 321 |
| `analysis/manifest.py` | `_manifest` | 210 |
| `analysis/export.py` | `export_lines` | 120 |

Quan hệ import: `hits`/`runs`/`rebuild`/`export` → `common`; `rebuild` →
`runs._create_run`; `export` → `manifest._manifest`; `runs` và `export` →
`app.services.metrics`. Không có circular import.

## Files changed

- Xóa `backend/app/services/analysis.py`.
- Thêm `backend/app/services/analysis/__init__.py`.
- Thêm `backend/app/services/analysis/common.py`.
- Thêm `backend/app/services/analysis/hits.py`.
- Thêm `backend/app/services/analysis/runs.py`.
- Thêm `backend/app/services/analysis/rebuild.py`.
- Thêm `backend/app/services/analysis/manifest.py`.
- Thêm `backend/app/services/analysis/export.py`.
- Thêm `backend/tests/test_analysis_imports.py`.
- Thêm `docs/cleanup/reports/p2-b2-analysis-split.md`.

Không file nào ngoài ownership bị thay đổi.

## Tests run

```text
$ backend/.venv/bin/ruff check backend/app backend/tests
All checks passed!

$ COMPOSE_PROJECT_NAME=eyelearning TEST_DB=eyetracking_test_b2 ./scripts/test_backend.sh
...
36 passed in 13.03s
[test_backend] OK
```

- 34 test cũ + 2 test import mới trong `test_analysis_imports.py`.
- Kiểm tra import trực tiếp:

```text
$ DATABASE_URL=... JWT_SECRET=... AI_HTTP_URL=... .venv/bin/python -c \
    "from app.services import analysis; from app.services.analysis import execute_pending_runs; ..."
ok: app.services.analysis.runs app.services.analysis.runs no_label
```

- Kiểm tra AST: 14/14 function trong bản gốc có mặt trong package và
  source segment giống hệt (`all identical: True`).

## Risks

- Các helper private (`_manifest`, `_filters`, ...) đổi module định nghĩa.
  Trong repo không có chỗ nào import trực tiếp các helper này; nếu sau này có
  thì cần import từ module mới (`analysis.manifest`, `analysis.common`, ...).
- Monkeypatch cấp module (`analysis.SessionLocal`, `analysis.metrics`) sẽ không
  còn tác dụng lên submodule. Repo hiện không dùng pattern này.
- `__init__.py` import eager cả 5 module, tương đương việc import một module
  đơn trước đây; không phát sinh chi phí import mới đáng kể.

## Follow-ups

- Không bắt buộc cho task này.
- P3 (ORM performance) có thể tối ưu `selectin`/`raiseload` trong
  `analysis/runs.py`, `analysis/rebuild.py`, `analysis/manifest.py`.
- Nếu public API mở rộng, cập nhật `__all__` và `test_analysis_imports.py`.
