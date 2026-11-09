# P3 — Chat/analysis/metrics: bỏ selectin/joined thừa

## Summary

- Sửa accidental heavy load trong `chat.py:_resolve_context`: câu
  `select(Enrollment)` kéo theo `Enrollment.course` (`lazy="joined"`), từ đó
  load tiếp `Course.owner`/`creator` (joined), `Course.versions`/`enrollments`
  (selectin), `CourseVersion.modules`/`items` (selectin),
  `CourseVersionModule.items` (selectin) và `User.roles` (selectin). Chỉ cần
  `enrollment.id`, nên thêm `raiseload(Enrollment.course)`.
- Thêm `raiseload(AnalysisRun.aoi_set)` phòng vệ ở `analysis/export.py` và 3
  call site `db.get(AnalysisRun, ...)` trong `analysis/runs.py`. Hiện không có
  code nào đọc `run.aoi_set`; raiseload biến lỗi tiềm ẩn thành lỗi sớm thay vì
  kéo cả `AoiSet.definitions` (selectin).
- Audit toàn bộ `db.get(...)` trong các file thuộc ownership. Các chỗ còn lại
  đã có raiseload đầy đủ hoặc không có quan hệ eager:
  - `analysis/manifest.py`: đã raiseload `LearningSession.presentations`,
    `Enrollment.course`, `CourseVersion.modules/items`,
    `Course.versions/enrollments/owner/creator`, `Lesson.versions/slides`,
    `LessonVersion.slides`, `AoiSet.definitions`.
  - `analysis/rebuild.py`: đã raiseload `Course.*` và
    `LearningSession.presentations`.
  - `course_students.py`: query tường minh, đã raiseload `Lesson.versions/slides`,
    `Enrollment.course`, `User.profile/roles`; không có N+1 (mọi dữ liệu được
    gom bằng bulk query trước vòng lặp).
  - `metrics.py:96` `db.get(ContentPresentation)` không có quan hệ
    selectin/joined nào → giữ nguyên.
- Thêm 4 query-count test mới (3 chat + 1 analysis manifest).

## Audit `db.get(...)`

| File | Entity | Quan hệ eager mặc định | Xử lý |
|---|---|---|---|
| `api/routes/chat.py` | `ChatSession` | `messages` selectin | đã có `raiseload(messages)` |
| `api/routes/chat.py` | `CourseVersion` | `modules`, `items` selectin | đã có raiseload |
| `api/routes/chat.py` | `Lesson` | `versions`, `slides` selectin | đã có raiseload |
| `api/routes/chat.py` | `LessonVersion` | `slides` selectin | đã có raiseload |
| `api/routes/chat.py` | `CourseVersionModule` | `items` selectin | đã có raiseload |
| `api/routes/chat.py` | `QuizAttempt`, `CourseVersionItem`, `QuizSpec` | không có eager | giữ nguyên |
| `api/routes/chat.py` | `Enrollment` (entity) | `course` joined → cả Course graph | **thêm `raiseload(course)`** |
| `services/analysis/export.py` | `AnalysisRun` | không eager, nhưng `aoi_set` là graph nặng | **thêm `raiseload(aoi_set)`** |
| `services/analysis/export.py` | `GazeBatch` | không eager | giữ nguyên |
| `services/analysis/runs.py` | `AnalysisRun` (3 chỗ) | không eager, `aoi_set` nặng | **thêm `raiseload(aoi_set)`** |
| `services/analysis/runs.py` | `AoiSet` | `definitions` selectin | đã có raiseload |
| `services/analysis/manifest.py` | `LearningSession` | `presentations` selectin | đã có raiseload |
| `services/analysis/manifest.py` | `Enrollment` | `course` joined | đã có raiseload |
| `services/analysis/manifest.py` | `CourseVersion` | `modules`, `items` selectin | đã có raiseload |
| `services/analysis/manifest.py` | `Course` | `versions`, `enrollments` selectin; `owner`, `creator` joined | đã có raiseload |
| `services/analysis/manifest.py` | `Lesson` | `versions`, `slides` selectin | đã có raiseload |
| `services/analysis/manifest.py` | `LessonVersion` | `slides` selectin | đã có raiseload |
| `services/analysis/manifest.py` | `AoiSet` | `definitions` selectin | đã có raiseload |
| `services/analysis/manifest.py` | `CourseVersionItem`, `Calibration`, `Device` | không eager | giữ nguyên |
| `services/analysis/rebuild.py` | `Course` | `versions`, `enrollments` selectin; `owner`, `creator` joined | đã có raiseload |
| `services/metrics.py` | `ContentPresentation` | không eager | giữ nguyên |

## Query counts

Đo bằng `tests/query_counter.count_queries(engine)` quanh request HTTP (bao gồm
2 query auth: user + roles). Riêng chat stream có thêm 1 INSERT `chat_sessions`.

| Path | Before | After | Test |
|---|---:|---:|---|
| `GET /api/courses/{id}/chat/sessions` | 6 | 6 | `test_list_sessions_query_count` |
| `GET /api/chat/sessions/{id}/messages` | 7 | 7 | `test_list_messages_query_count` |
| `POST /api/courses/{id}/chat/stream` (resolve context) | **16** | **12** | `test_chat_stream_context_query_count` |
| `analysis.export_lines` (manifest line) | 12 | 12 | `test_analysis_manifest_query_count` |
| `GET /teacher/courses/{id}/students` (đo scratch, không commit) | 8 | 8 | — |

Course students: seed 1 lesson không slide = 8 query; nếu có slide thì thêm 1
query metrics (9), vẫn trong budget ≤ 10. Không có N+1 vì mọi dữ liệu được gom
bằng bulk query trước vòng lặp.

Trước fix, 5 query thừa phát sinh ở chat stream:

1. `SELECT enrollments ... LEFT JOIN courses ... LEFT JOIN teacher_profiles ...
   LEFT JOIN users ... LEFT JOIN user_profiles ...` (do `Enrollment.course`
   joined).
2. `SELECT user_roles ...` (selectin từ `Course.creator`).
3. `SELECT course_versions ...` (selectin từ `Course.versions`).
4. `SELECT course_version_modules ...` (selectin từ `CourseVersion.modules`).
5. `SELECT course_version_items ...` + `SELECT course_version_modules_1 ...`
   (selectin dây chuyền từ `CourseVersion.items` và
   `CourseVersionModule.items`).

Đồng thời, trước fix `db.get(CourseVersionModule, item.module_id)` được trả từ
identity map (vì selectin đã load sẵn modules), nên không phát sinh query; sau
fix nó chạy 1 query riêng. Net: 16 → 12.

Sau fix, 12 query còn lại đều cần thiết: auth (2), course, enrollment id,
chat access, course version, enrollment entity (plain), course version item,
lesson, lesson version, module, INSERT session.

## Files changed

- `backend/app/api/routes/chat.py` — `raiseload(Enrollment.course)` trong
  `_resolve_context`.
- `backend/app/services/analysis/export.py` — `raiseload(AnalysisRun.aoi_set)`.
- `backend/app/services/analysis/runs.py` — `raiseload(AnalysisRun.aoi_set)` ở
  `execute_run` (2 chỗ) và `get_run_result`.
- `backend/tests/test_chat_queries.py` (mới) — 3 query-count test.
- `backend/tests/test_analysis_queries.py` (mới) — 1 query-count test.
- `docs/cleanup/reports/p3-p3-chat-analysis.md` (mới).

Không file nào ngoài ownership bị thay đổi. Không đổi API path, response shape,
status code hay auth behavior.

## Tests run

```text
$ backend/.venv/bin/ruff check backend/app backend/tests
All checks passed!

$ COMPOSE_PROJECT_NAME=eyelearning TEST_DB=eyetracking_test_p3 ./scripts/test_backend.sh
...
54 passed in 15.30s
[test_backend] OK
```

- 50 test cũ + 4 test query-count mới.
- `test_chat_queries.py`: 3 passed.
- `test_analysis_queries.py`: 1 passed.

## Risks

- `raiseload` đổi hành vi lazy-load thành raise. Nếu sau này code đọc
  `enrollment.course` trên object trả về từ `_resolve_context`, hoặc đọc
  `run.aoi_set` trên object trả về từ `export_lines`/`execute_run`/
  `get_run_result`, sẽ nhận `InvalidRequestError` thay vì tự động query. Hiện
  không có chỗ nào làm vậy; đây là chủ ý để phát hiện sớm.
- Query-count test phụ thuộc vào số query auth hiện tại (2). Nếu auth thêm query
  hợp lệ, các ngưỡng 8/9/13/14 vẫn còn headroom; nếu vượt, cần cập nhật test
  cùng lúc với thay đổi auth.
- `tests/query_counter.py` là context manager đồng bộ (docstring ví dụ dùng
  `async with`). Test mới dùng `with`; không sửa file này vì thuộc P4.

## Follow-ups

- P4: sửa docstring/ví dụ `query_counter.py` cho khớp context manager đồng bộ,
  hoặc bổ sung biến thể async nếu cần.
- P4: có thể thêm query-count test cho `GET /teacher/courses/{id}/students`
  (hiện đo scratch = 8, budget ≤ 10) và các endpoint media/quiz.
- Nếu profiling cho thấy `metrics.compute_presentation_metrics` tốn chi phí load
  entity, có thể thay `db.get(ContentPresentation)` bằng
  `select(ContentPresentation.id)`; hiện chưa cần vì không có eager load.
