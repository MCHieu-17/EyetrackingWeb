# TEST_PLAN.md — Khóa hành vi hiện tại

> Trạng thái: **đã triển khai** (2026-11-20).
> Phạm vi: Backend LMS, Eyetracking, Chatbot/RAG, Frontend E2E.
> Mục tiêu: viết test **hộp đen** để khóa hành vi đang chạy, làm lưới an toàn cho
> các đợt refactor/tối ưu tiếp theo.
>
> Kết quả chạy trên máy local:
> - Backend fast: **79 passed** (~53s)
> - Gaze fast: **22 passed**; gaze smoke: **1 passed** (~5s, CPU)
> - Chatbot fast: **22 passed**; chatbot RAG smoke: **1 passed** (~24s)
> - Playwright: **9 passed** (gồm flow chat thật khi `E2E_CHAT=1`)
> - `make check-full` và `./scripts/test_migrations.sh` pass.

---

## 0. Tóm tắt điều hành

- Toàn bộ test cũ đã bị xoá khỏi working tree (backend `tests/`, gaze `tests/`,
  chatbot `tests/`, frontend `*.test.*`, `e2e/`, config Vitest/Playwright).
  Kế hoạch này dựng lại bộ test từ đầu, theo hợp đồng HTTP/WS/DB hiện tại.
- Chia 2 nhóm:
  - **`fast`**: mock toàn bộ model/LLM/VLM/embedding; dùng PostgreSQL + Redis
    thật; chạy sau mỗi lần sửa, mục tiêu < 3 phút.
  - **`smoke`**: chạy model thật (UniGaze/MediaPipe, embedding Qwen3, VLM/LLM)
    trên stack thật; chạy trước khi merge/release, mục tiêu < 10 phút.
- Frontend chỉ có **E2E smoke** (Playwright), không viết unit test UI chi tiết.
- Có 3 điểm phải sửa kỳ vọng so với đề bài, vì code hiện tại khác:
  1. **Không còn LangGraph.** Pipeline chatbot là tuyến tính
     (`query prep → retrieval → generation → citation gate`). Test khóa
     hợp đồng SSE/hành vi, không test node graph.
  2. **Không có chunking.** Mỗi slide là một document duy nhất trong
     `v_chatbot_slide_documents`; ingest ghi nguyên `transcript` vào `slides`.
  3. **Không dùng sklearn.** Calibration là hồi quy tuyến tính `numpy.linalg.lstsq`,
     serialize `.ubj` format `gaze-lr-v2`. Test hồi quy thật qua HTTP, không cần
     thêm scikit-learn.

---

## 1. Nguyên tắc viết test

### 1.1 Hộp đen thật sự

Chỉ quan sát:

- HTTP: status code, header quan trọng (`Retry-After`, `Cache-Control`,
  `Content-Disposition`), JSON camelCase, SSE frame.
- WebSocket: frame gửi/nhận, close code, echo metadata.
- DB: hàng/cột sau thao tác (dùng SQL thuần), không đọc object ORM nội bộ.
- File/media: file tồn tại/không tồn tại, bytes trả về.

Không gọi trực tiếp:

- hàm private (`_resolve_legacy_view`, `_stream_with_citation_gate`, …),
- hàm tính toán nội bộ (`metrics._count_fixations`, `rrf_fuse`, …),
- class nội bộ (`Calibration`, `SessionManager`, `Ingestion`, `Retriever`).

Ngoại lệ được phép, coi là **ranh giới test double**:

- thay `app.api.session.runtime` bằng runtime giả cho gaze;
- thay factory provider (`get_vlm`, `get_embedding`, `get_llm_client`,
  `get_retriever`) bằng fake;
- chặn HTTP ra ngoài bằng `respx`;
- gọi entrypoint worker đã có (`process_pending_slide_imports`,
  `process_pending_jobs`, `execute_pending_runs`) qua adapter mỏng
  `tests/support/workers.py`.

Nếu refactor đổi các entrypoint này, chỉ sửa adapter, không sửa hàng trăm test.

### 1.2 Fixture được dùng SQL

Việc dựng precondition (course published, slide ready, session hết hạn, …)
được phép dùng SQL trực tiếp. Đây là setup, không phải thứ đang được khóa.
Assertion cuối cùng vẫn phải qua API/DB như người dùng thật.

### 1.3 Không khóa implementation

- Không assert số câu SQL, tên hàm, thứ tự gọi nội bộ.
- Không assert timestamp tuyệt đối; chỉ assert thứ tự, khoảng, hoặc `>=`.
- Không assert toàn bộ JSON body; chỉ assert field hợp đồng + field bắt buộc.
- Không phụ thuộc thứ tự key JSON.

---

## 2. Đối chiếu code hiện tại

### 2.1 Trạng thái test

| Khu vực | Hiện tại | Việc cần làm |
|---|---|---|
| `backend/tests/` | Không tồn tại (đã xoá) | Dựng lại từ đầu |
| `services/gaze/tests/` | Không tồn tại | Dựng lại |
| `services/chatbot/tests/` | Không tồn tại | Dựng lại |
| `frontend/*.test.*` | Không còn | **Không** dựng lại unit test |
| `frontend/e2e/` | Không tồn tại | 5 flow smoke |
| `playwright.config.ts` | Đã xoá | Khôi phục |
| dev deps | backend/chatbot/gaze chỉ còn `ruff`; frontend không còn Playwright | Bổ sung có duyệt |

### 2.2 Hợp đồng cần đặc biệt chú ý

- Backend fail-fast nếu `app_metadata.schema_generation != '13'`; test DB phải
  migrate bằng `db/migrate.sh`, không dùng `create_all()`.
- 24 bảng lõi gồm `app_metadata`; `schema_migrations` không tính.
- Auth hybrid: access token trong memory/`Authorization`, refresh trong cookie
  httpOnly; request state-changing bằng cookie phải có `X-CSRF-Token`.
- `presentationId = content_views.id`; `sequence_no` do server cấp.
- `enteredAt` bị kẹp `[now - 5 phút, now]`; request trễ hơn view mới nhất quá
  250ms trả `409 stale_presentation`.
- Session đóng vẫn nhận gaze trong **2 phút** (`CLOSE_GRACE`) rồi mới 409.
- `tracked_duration_ms` (theo sample) khác `dwell_ms` (wall time). Ngưỡng
  `CONTENT_VIEW_MIN_DWELL_MS` chỉ phân loại/lọc.
- Metrics version hiện tại: `gaze-metrics-v8`; heatmap 24×24 row-major.
- Chatbot không có chunking; mỗi slide = một document.
- Chatbot `_DOC_COLUMNS`/citation dùng `slides.id` làm `document_id`/`slide_id`.

### 2.3 Rủi ro phát hiện khi đọc code (ghi nhận, chưa sửa)

| Rủi ro | Chi tiết | Xử lý trong kế hoạch |
|---|---|---|
| `/internal/metrics` không auth | Ai gọi được backend cũng đọc pool/queue; nginx chặn `/internal/` từ ngoài | Test khóa hành vi hiện tại; ghi chú bảo mật, không đổi code |
| `/ai/health` không auth | Proxy chỉ gọi `/ready` của gaze | Test schema; không mở rộng |
| Rate limit gaze no-op khi không có Redis | `increment()` trả `None` → không chặn | Fast test dùng Redis test DB 15 |
| E2E không có `data-testid` | Phải dùng role/label/text | Chấp nhận; label là hợp đồng người dùng |
| Ingest không có endpoint xoá | Xoá qua cascade/replace PDF | Test xoá/ thay thế ở backend + view chatbot |

Hai lỗi sản phẩm được test phát hiện và đã sửa tối thiểu trong lần triển khai:

1. `backend/app/services/content/publish.py`: `dict(rows)` với 3 cột gây
   `ValueError`/HTTP 500 khi course có slide. Đổi sang dict comprehension.
2. `GazeBatchCreateIn.batch_id` nhận chuỗi bất kỳ nhưng cột DB là UUID, gây 500
   với input sai. Đổi schema sang `UUID`; `GazeBatchAckOut` trả string.

---

## 3. Kiến trúc test & hạ tầng

### 3.1 Cây file dự kiến

```text
backend/tests/
  conftest.py
  support/
    api.py            # client theo role, login, cookie/CSRF
    db.py             # truncate, SQL helpers
    factories.py      # seed qua API + SQL cho precondition
    workers.py        # adapter gọi worker entrypoint 1 lượt
    fake_chatbot.py   # SSE/JSON giả cho backend
  fast/
    test_auth.py
    test_courses_content.py
    test_publish.py
    test_visits_sessions.py
    test_presentations_layouts.py
    test_gaze_ingest.py
    test_quiz.py
    test_aoi_editor.py
    test_metrics.py
    test_analytics.py
    test_chat_proxy.py
    test_maintenance.py
    test_schema_contract.py
  pytest.ini

services/gaze/tests/
  conftest.py
  fast/
    test_health_ready.py
    test_session_api.py
    test_calibration_regression.py
    test_stream_ws.py
  smoke/
    test_model_smoke.py
  fixtures/
    face_sample.jpg
    README.md          # nguồn + license ảnh
  pytest.ini

services/chatbot/tests/
  conftest.py
  support/
    db.py
    fakes.py           # FakeEmbeddings, FakeVLM, FakeLLM
    seed.py
  fast/
    test_ingest_api.py
    test_ingest_failures.py
    test_query.py
  smoke/
    test_rag_smoke.py
  pytest.ini

frontend/
  playwright.config.ts
  e2e/
    support/
      fixtures.ts       # đọc .fixtures.json, login helpers
      seed-api.ts       # tạo/xoá course qua API cho flow giáo viên
    auth-roles.spec.ts
    teacher-content.spec.ts
    student-learning-quiz.spec.ts
    teacher-analytics.spec.ts
    student-chat.spec.ts   # optional, gate E2E_CHAT=1

scripts/
  test_backend.sh
  test_gaze.sh
  test_chatbot.sh
  test_fast.sh
  test_smoke.sh
  seed_e2e.py
  e2e.sh
```

### 3.2 Marker và nhóm chạy

| Marker | Ý nghĩa | Dùng model thật? | Chạy khi nào |
|---|---|---|---|
| `fast` | API/DB/WS với model/LLM giả | Không | Sau mỗi lần sửa |
| `smoke` | Model/LLM thật, stack thật | Có | Trước merge/release |
| `db` | Cần PostgreSQL test | Không | Trong `fast` |
| `redis` | Cần Redis test DB 15 | Không | Trong `fast` |
| `gpu` | Cần UniGaze/MediaPipe weights + GPU (hoặc CPU rất chậm) | Có | `smoke` |

Quy ước:

- `pytest -m "fast"` là mặc định của `scripts/test_fast.sh`.
- `pytest -m "smoke"` **không** tự chạy trong `fast`.
- Một test smoke phải tự `skip` kèm lý do rõ nếu thiếu weights/token/stack,
  nhưng CI pre-merge phải fail nếu biến `REQUIRE_SMOKE=1`.

### 3.3 Cô lập DB backend/chatbot

- Một database test dùng chung: `eyetracking_test`, tạo mới mỗi lần chạy
  `scripts/test_backend.sh` / `scripts/test_chatbot.sh`, migrate bằng image
  `migrate` (rebuild trước).
- `TEST_DATABASE_URL` đặt **trước khi import app**.
- Giữa các test: `TRUNCATE` toàn bộ bảng public trừ `schema_migrations` và
  `app_metadata`, `RESTART IDENTITY CASCADE`.
- Redis: dùng DB 15 (`REDIS_URL=redis://127.0.0.1:6379/15`), `FLUSHDB` trước
  mỗi test. Script bật `docker compose up -d redis` và fail sớm nếu không ping
  được.
- Media: `MEDIA_DIR` trỏ temp dir mới mỗi session; xoá giữa các test.
- Rate limit in-memory: reset `app.core.ratelimit._BUCKETS` trong fixture
  (phòng trường hợp Redis lỗi).
- Không chạy song song ở giai đoạn đầu (một DB, một Redis DB). Nếu sau này cần
  `pytest-xdist`, mỗi worker phải có DB/Redis namespace riêng.

### 3.4 Mock tại biên

| Thành phần | Cách mock | Không mock |
|---|---|---|
| Backend → chatbot | `respx` chặn `POST /chat/stream` | Auth/SSE/DB persistence của backend |
| Backend → gaze `/ai/health` | `respx` | Route/proxy schema |
| OTP email | DEBUG=true + OTP_DEV_ECHO=true, đọc mã từ `caplog` | Toàn bộ flow OTP/DB |
| Chatbot VLM | Fake object có `with_structured_output().invoke()` | Ingest DB, PDF render, metadata |
| Chatbot embedding | Fake trả vector 1024 chiều xác định | Retrieval SQL/BM25/pgvector/RRF |
| Chatbot LLM | Fake có `.structured()` và `.stream()` | SSE framing, citation gate |
| Chatbot backend LMS | `respx` chặn `/internal/chat/lms-query` | Detect/render LMS |
| Gaze runtime | Fake runtime trả pitch/yaw theo bytes ảnh | Session API, calibration thật, WS protocol |
| Gaze model | Không mock ở smoke | UniGaze/MediaPipe thật |

### 3.5 Fixture dùng chung

Backend:

- `client`: `httpx.AsyncClient` + `ASGITransport`, chạy lifespan một lần/session.
- `login_as(role)` → client có cookie/header; `auth_headers`.
- `course_factory`, `lesson_factory`, `quiz_factory`, `slide_factory`:
  ưu tiên gọi API; fallback SQL cho `index_status`, timestamp, metrics.
- `gaze_factory`: tạo visit/session/presentation/layout/samples bằng API,
  sau đó chạy worker adapter.
- `job_state(job_id)`, `count_rows(sql)`.
- `freeze_expiry`: UPDATE `expires_at`/`last_seen_at` bằng SQL.

Chatbot:

- `chatbot_client`: ASGI client, lifespan, env dummy.
- `db_seed_course`: course/module/lesson/slide/media published + ready.
- `fake_vlm`, `fake_embedding`, `fake_llm` fixture monkeypatch factory.
- `temp_media`: chứa PDF 2 trang; env `LOCAL_MEDIA_DIR`.
- `clean_globals`: đóng pool/retriever/ingestion, clear `lru_cache`.

Gaze:

- `fake_runtime`: thay `app.api.session.runtime`; hỗ trợ mode `ok`, `no_face`,
  `invalid_image`, `overload`, `not_ready`; map bytes → (pitch, yaw).
- `client`: `TestClient(app)` **không dùng context manager** để tránh lifespan
  load model thật trong fast test.

### 3.6 Lệnh chạy

Test chạy trong image test riêng (`backend-test`, `chatbot-test`, `gaze-test`)
để không cần venv host và không cài pytest vào image production. Compose service
dùng `profiles: ["test"]`.

```bash
# Toàn bộ fast (backend + gaze + chatbot), dùng DB/Redis test
./scripts/test_fast.sh

# Riêng từng service
./scripts/test_backend.sh
./scripts/test_gaze.sh fast
./scripts/test_chatbot.sh fast

# Chạy một file
cd backend && TEST_DATABASE_URL=... REDIS_URL=... .venv/bin/pytest \
  tests/fast/test_quiz.py -q

# Smoke trước merge (stack + weights + LLM thật)
./scripts/test_smoke.sh
./scripts/test_gaze.sh smoke
./scripts/test_chatbot.sh smoke
./scripts/e2e.sh
```

`make` target đề xuất:

```make
test-fast:  ./scripts/test_fast.sh
test-smoke: ./scripts/test_smoke.sh
```

---

## 4. Phần 1 — Backend LMS (FastAPI + Postgres/Redis)

### 4.1 Ma trận phân quyền cần khóa

| Vai trò | Được phép | Bị từ chối (mã mong đợi) |
|---|---|---|
| Anonymous | `/health`, `/api/health`, `/api/config`, `/api/auth/*` | endpoint cần auth → `401` |
| Student | course-visits, learning-sessions, presentations, layouts, gaze-batches, quiz attempts, chat, calibration, `/api/me/*`, `/api/courses/{id}` nếu published | teacher/admin routes → `403`; session/visit của người khác → `403`; quiz khóa khác → `403` |
| Teacher (owner) | toàn bộ `/teacher/courses/{id}/**`, AOI slide thuộc khóa, analytics | khóa người khác → `403`; `/admin/**` → `403` |
| Teacher (assigned qua `course_teachers`) | xem tree, students, analytics, slides | mọi thao tác ghi/publish/delete → `403` |
| Admin | toàn bộ teacher routes + `/admin/**` | không có (trừ dữ liệu không tồn tại → `404`) |
| Internal token | `/internal/chat/lms-query` đúng token | sai/thiếu token → `401`; context mismatch → `403` |

Ghi chú: một số route cố tình trả `404` thay vì `403` để tránh lộ tài nguyên
(ví dụ lesson không tồn tại/không thuộc khóa). Test phải khóa đúng mã hiện tại.

### 4.2 `test_auth.py`

| Case | Input → kỳ vọng |
|---|---|
| Login thành công | `POST /api/auth/login` đúng seed → `200`, `accessToken/refreshToken/tokenType/user`, set 3 cookie `access_token`, `refresh_token`, `csrf_token`; `csrf_token` không httpOnly |
| Login sai | sai mật khẩu / email lạ → `401` cùng message `Email hoặc mật khẩu không đúng` |
| Tài khoản disabled/deleted | `status != active` hoặc `deleted_at` → `401` |
| Bearer auth | `GET /api/me/profile` với `Authorization` → `200` |
| Cookie auth + CSRF | `POST /api/me/profile` bằng cookie không CSRF → `403`; có `X-CSRF-Token` → `200` |
| Refresh rotation | refresh cũ → cặp mới; dùng lại refresh cũ → `401` |
| Logout | revoke refresh hiện tại; refresh sau logout → `401`; cookie bị xoá |
| Change password | sai mật khẩu hiện tại → `400`; thành công thu hồi session khác, giữ session hiện tại; mật khẩu mới đăng nhập được |
| OTP request | email sai domain/mã SV → `422 {code:"invalid_email"}`; email hợp lệ + SMTP trống + DEBUG/OTP_DEV_ECHO → `200 delivery="dev"`; cooldown 60s → `429 + Retry-After` |
| OTP verify | đúng mã → `200` token + tạo user nếu chưa có + `student_profiles.student_code`; sai mã tăng `attempts`; hết hạn → `400 otp_expired`; dùng lại → `400 otp_consumed`; quá 5 lần → `400 otp_too_many_attempts` |
| OTP single active | request lần 2 sau cooldown làm challenge cũ `invalidated_at`; challenge cũ verify → `otp_consumed` |
| Register | `POST /api/auth/register` → `403` (đã tắt) |

### 4.3 `test_courses_content.py`

| Case | Input → kỳ vọng |
|---|---|
| Tạo khóa | teacher → `201`, `status=draft`, `isOwner=true`, `showGazeDot=false`, `requireCalibration=true` |
| List/filter | `GET /teacher/courses?status=&q=&limit=&offset=` lọc đúng, không lộ khóa người khác |
| Update metadata | owner đổi title/description/status; `status` sai pattern → `422` |
| Gaze-dot / require-calibration | `PATCH` trả `{ok, showGazeDot|requireCalibration}`; đổi `requireCalibration` xoá cache enrollment |
| Module | tạo `201` position nối tiếp; sửa/xoá; xoá module cascade lesson/slide |
| Lesson | tạo `201`; sửa title; xoá cascade; không nhận PDF cho lesson `quiz` |
| Quiz item | tạo `201` `kind=quiz`, `quizStatus=draft`, chèn `afterId` đúng vị trí |
| Reorder | gửi đủ danh sách item → `200`; thiếu item → `400`; item khóa khác → `400` |
| Student directory | `GET /teacher/students?q=` tìm theo tên/mã/email, chỉ student active |
| Add students | chỉ thêm student active; id trùng bỏ qua; id sai bỏ qua; trả `added` |
| Remove student | set `enrollments.status='dropped'`; xoá lại → `404` |
| Delete course | cascade toàn bộ module/lesson/slide/aoi/enrollment/visit/session/view/sample/quiz/chat/job; media xoá sau commit |
| Tree | `GET /teacher/courses/{id}` trả `slides`, `slidesReady/Failed/Pending`, quiz meta đúng |

### 4.4 `test_publish.py`

| Case | Input → kỳ vọng |
|---|---|
| Không có chương | publish → `400 {code:"content_invalid"}` |
| Có chương, không có lesson | `400 content_invalid` |
| Lesson không có slide | `400 content_invalid` message chứa tên bài |
| Slide chưa `ready` | asset ready nhưng `index_status=pending` → `409 slides_not_indexed`; đồng thời enqueue `index_slides` cho course |
| Media asset chưa ready | `400 content_invalid` |
| Quiz không câu hỏi | `400 quiz_not_ready` |
| Quiz thiếu đáp án/points <= 0/trùng ID | `400 quiz_not_ready` |
| Publish thành công | `courses.status='published'`, `published_at` set; outline student đọc được |
| Publish lại | idempotent, không nhân đôi dữ liệu |
| Quiz `PATCH status=published` | gọi publish course; nếu course chưa đủ điều kiện → lỗi và **không** commit quiz published |
| Publish bởi assigned teacher | `403` |
| Publish bởi admin | `200` |

### 4.5 `test_visits_sessions.py`

| Case | Input → kỳ vọng |
|---|---|
| Visit idempotent | cùng `(enrollmentId, visitKey)` → cùng `id`, `201` |
| Visit active | `GET /api/course-visits/active?enrollmentId=` trả visit active mới nhất hoặc `null` |
| Visit heartbeat | cập nhật `last_seen_at`; visit đã đóng → `409 visit_closed` |
| End visit | status `ended`, `ended_at` set; đóng mọi content view mở; gọi lại idempotent |
| Visit người khác | `403`; enrollment dropped → `403` |
| Session tạo mới | `201`, `status=in_progress`, `mode=first`, `expiresAt ≈ now+12h`, `calibrated=false` nếu không có calibration |
| Session continue | cùng enrollment/lesson/viewport/calibration/visit → cùng `id`, `201 mode=continue` |
| Đổi viewport/calibration | session cũ `aborted`, view mở bị đóng, tạo session mới |
| Thiếu calibration | course `requireCalibration=true` + không có model → `409 {code:"calibration_required"}` |
| Khóa archived | `409 course_archived` |
| Lesson chưa publish | `404` |
| Enrollment dropped | `403` |
| Visit không thuộc enrollment | `400 visit_conflict` |
| Visit đã đóng | `409 visit_closed` |
| CourseVisitId bỏ trống | tự dùng/tạo visit active |
| Session contents | owner → danh sách slide; student khác → `403`; lesson không tồn tại → `404` |
| End session | `completed|aborted`; đóng view; enqueue `analyze_lesson`; gọi lại → `409 session_closed` |
| TTL | session `expires_at` qua khứ → maintenance chuyển `expired`, đóng view, enqueue analyze |

### 4.6 `test_presentations_layouts.py`

| Case | Input → kỳ vọng |
|---|---|
| Tạo presentation | `201`, `sequenceNo` bắt đầu `0`, `startedAt` ISO |
| Cùng `clientPresentationId` + cùng context | trả cùng `id`, không tạo row mới, vẫn `201` |
| Cùng UUID + khác slide/surface/session | `409 presentation_conflict` |
| UUID mới, quay lại slide cũ | tạo row mới, `sequenceNo = max+1` |
| `enteredAt` cũ > 5 phút | kẹp về `now-5m`; DB `started_at` đúng khoảng |
| `enteredAt` tương lai | kẹp về `now` |
| `enteredAt` cũ hơn view mới nhất > 250ms | `409 stale_presentation` |
| Legacy không UUID, `sequenceNo` trùng + cùng context | trả row cũ |
| Legacy `sequenceNo` trùng + khác slide | cấp sequence mới, không gán nhầm slide |
| Slide không thuộc lesson | `400` |
| Session đã đóng > 2 phút | `409 session_closed`; trong 2 phút vẫn nhận |
| Layout lần đầu | `201`, `layoutGeneration` đúng, `elements` lưu normalized |
| Layout trùng `layoutGeneration` | trả cùng `id`, không tạo row |
| `coordinateSpace=original-v1` | `409` |
| Alias `semanticCode` | chấp nhận, lưu `code` |
| Presentation người khác | `403` |

### 4.7 `test_gaze_ingest.py`

| Case | Input → kỳ vọng |
|---|---|
| Batch hợp lệ | `stored=N`, `duplicate=0`, `rejected=0`; DB đúng `viewport_x/y`, `status`, `quality_flags` |
| Retry cùng batch | `stored=0`, `duplicate=N`; không nhân đôi row |
| Sequence ngoài range | `422` |
| Sequence không tăng dần | `422` |
| `status=ok` thiếu x/y | `422` |
| `status!=ok` có x/y | `422` |
| Presentation/layout khác session | `400 batch_conflict` |
| > 2000 sample | `422` (Pydantic) |
| Batch rỗng | `422` |
| Rate limit | > 120 batch/phút/user/session → `429 + Retry-After` (Redis) |
| `analysis_status` | batch mới set `content_views.analysis_status='pending'` |
| Session đóng | > 2 phút → `409` |

### 4.8 `test_quiz.py`

| Case | Input → kỳ vọng |
|---|---|
| Student xem đề | `correctOptionIds=[]`, `explanation=""`, không lộ đáp án |
| Teacher xem đề | thấy `correctOptionIds`, `explanation` |
| Sau khi nộp | student thấy đáp án đúng/giải thích |
| Start attempt | `201`, `attemptNo=1`, `status=in_progress`, `expiresAt` theo `durationMinutes`/`dueAt` |
| Start lần 2 | trả cùng attempt in_progress |
| Submit | chấm all-or-nothing; `score`, `maxScore`, `grading` đúng; `submittedAt` set |
| Submit sai định dạng answers | `422` |
| Submit attempt người khác | `403` |
| Submit quá hạn | set `expired`, `409 attempt_expired` |
| Submit lần 2 | `409 attempt_submitted` |
| Retry khi `allowRetry=false` | `403` |
| Retry khi `allowRetry=true` | `201`, `attemptNo+1`, snapshot mới |
| Start sau submit, `allowRetry=false` | `409 attempt_submitted` |
| Snapshot bất biến | sửa `quiz_config` sau khi start; submit vẫn dùng snapshot cũ |
| Quiz thuộc khóa chưa publish | start → `404` (khóa chưa xuất bản) |
| Quiz config `status=draft` nhưng khóa đã publish | API hiện vẫn cho start `201`; ghi nhận hành vi, UI không auto-start |
| Khóa archived | `409 course_archived` |
| List attempts | student chỉ thấy của mình; teacher thấy của khóa mình; người khác `403` |

### 4.9 `test_aoi_editor.py`

| Case | Input → kỳ vọng |
|---|---|
| Lưu slide AOI | replace toàn bộ; tự thêm `no_label`; trả definitions sorted theo `code` |
| Nhãn sai | `label` không khớp `^AOI_[A-Z0-9_]{1,60}$` → `400` |
| Nhãn trùng | `400` |
| Nhãn thiếu | tự cấp `AOI_n` kế tiếp |
| Geometry slide | thiếu `xMin..` / ngoài [0,1] / min>=max → `400` |
| Code trùng | `400` |
| Container/leaf | container label NULL; leaf có label; parent-child set đúng |
| UI generate | merge mặc định; code đã có bỏ qua; geometry selector `[data-aoi='code']` |
| UI save | tên trùng (casefold) → `400`; tên bắt đầu `SLIDE_`/`UI_NO_LABEL` → `400`; container được phép geometry rỗng |
| Quyền | student → `403`; assigned teacher không sở hữu → `403`; owner/admin → `200` |
| Enqueue | lưu slide AOI → `analyze_lesson` cho lesson; lưu UI → chỉ view có sample |
| Rebuild | trả `runs = số lesson` (hành vi hiện tại), set view `pending`, enqueue job |

### 4.10 `test_metrics.py`

Test bằng cách tạo session/presentation/layout/samples qua API, chạy worker
adapter, rồi đọc DB + API. Không gọi `analyze_content_view`.

| Case | Input → kỳ vọng |
|---|---|
| Map viewport → slide | layout `left/top/width/height`; `slide_x/y` đúng công thức |
| Ngoài slide | `slide_x/y` ngoài [0,1] → `SLIDE_NO_LABEL`, không cộng heatmap |
| Thiếu layout | `quality_flags.layout_missing=true`, `slide_x/y=NULL`, nhãn UI |
| Quiz surface | không map slide; nhãn UI/`UI_NO_LABEL` |
| Một nhãn/sample | không cộng container; ưu tiên custom > text > table > image > drawing > system; cùng hạng chọn diện tích nhỏ hơn |
| Heatmap | chỉ sample ok trong slide; 24×24; `grid[y][x]`; tổng = `on_slide_gaze_count` |
| Tracked duration | chỉ cộng gap `0..max(250, ceil(3000/FPS))` giữa 2 sample ok |
| Gap âm/quá lớn/status lỗi | không cộng |
| `aoi_stats` | `ms` cộng gap cho nhãn sample; `samples` đếm sample ok có nhãn |
| Fixation | cụm >= 2 điểm trong bán kính 0.03; đếm đúng |
| Version | `analysis_version='gaze-metrics-v8'`, `analysis_status='ready'`, `analyzed_at` set |
| View rỗng | metrics = 0, grid rỗng, status ready (không lỗi) |
| Phân tích lại | sửa AOI → view `pending` → job mới; không xoá gaze thô |
| Worker lỗi 1 view | view đó `failed`, view khác vẫn `ready`; job ghi lỗi/retry đúng |

### 4.11 `test_analytics.py`

| Case | Input → kỳ vọng |
|---|---|
| `GET /teacher/courses/{id}/visits` | phân trang, lọc student/from/to; `includeShort=false` chỉ tính view >= ngưỡng; `lessonSessionCount` không phụ thuộc filter |
| `GET /teacher/students/{id}/visits` | chỉ khóa được chỉ định; quyền như trên |
| `GET /teacher/visits/{id}/gaze` | lọc `slideId`, `aoiLabel`; sort `event_time, sequence`; join đúng lesson/slide |
| `GET /teacher/visits/{id}/replay` | trả `visit`, `student`, `course`, `views`, `uiAois`; mỗi view có `dwellMs`, `counted`, layout, `aoiStats` |
| `GET /teacher/visits/{id}/samples` | keyset `afterTime+afterId`; thiếu một trong hai → `422`; contentView khác visit → `404`; `nextCursor` đúng |
| `GET /teacher/visits/{id}/summary` | tổng `gazeCount`, `onSlide`, `tracked`, `fixation`; `shortViewCount` luôn đếm toàn bộ; `includeShort=false` loại view ngắn |
| `POST .../analytics/aoi-summary` | filter student/visit/lesson/time/surface; `includeShort`; share; stale count; không lộ khóa khác |
| `POST .../analytics/heatmap` | chỉ view ready + đúng version + grid đủ; trả `onSlideSampleCount`, `analyzedViewCount`; version sai → stale |
| Export visit | `application/x-ndjson`, `Content-Disposition`, mỗi dòng JSON phẳng |
| Export lesson | `404` nếu chưa có view; `scope=slide|ui`; `404` sai scope → `422` |
| Quyền | assigned teacher xem được; teacher khác `403`/`404`; student `403` |

### 4.12 `test_chat.py`

`respx` giả `/chat/stream` của chatbot.

| Case | Input → kỳ vọng |
|---|---|
| Chat access | student chưa enroll → `403`; quiz đang mở `allowChatbot=false` → `403` và `blockedUntil`; sau submit → `200` |
| Tạo session + stream | SSE bắt đầu `event: session`, chuyển tiếp `status/token/citations/done`; lưu `chat_messages` student + assistant |
| Chatbot chưa cấu hình | trả stream `event: error` message cố định |
| Chatbot lỗi/HTTP 5xx | `event: error` message cố định, không lộ stack |
| Session list | `canContinue` đúng theo `contextKey`; filter `assignmentId/attemptId`; limit/offset |
| Rename | cập nhật title, trim; session người khác → `404` |
| Delete | xoá messages + session; người khác `404` |
| Messages | sort `createdAt`; limit/offset; không lộ session người khác |
| Rate limit | > 1 tin/5s/user → `429`; > 20/phút/IP → `429` |
| Draft answers | `draftAnswers` sai câu/option → `400`; hợp lệ được đưa vào context; `supportMode` là `review` khi attempt đã nộp, ngược lại `hint` |
| Attempt context | không truyền attempt/lesson nhưng có đúng 1 attempt đang mở → tự dùng attempt đó; có >1 → `400` |

### 4.13 `test_maintenance.py`

| Case | Input → kỳ vọng |
|---|---|
| Auth session hết hạn | xoá row |
| Learning session quá `expiresAt` | status `expired`, `ended_at` set, view mở đóng tại cutoff, enqueue analyze |
| Visit idle > 30 phút | status `expired`, session con `expired`, view đóng, enqueue analyze |
| OTP hết hạn > 1 ngày | xoá; OTP mới hơn giữ |
| Gaze retention | xoá sample cũ hơn `GAZE_RETENTION_DAYS`; `0` tắt |
| Transaction | một bước lỗi không làm mất các bảng khác (P1) |

### 4.14 `test_schema_contract.py`

| Case | Kỳ vọng |
|---|---|
| 24 bảng | đúng 24 bảng public, không tính `schema_migrations`/view |
| Generation | `app_metadata.schema_generation='13'` |
| Bảng cấm | không có `oauth_accounts`, `aoi_codes`, `aoi_suggestions` |
| Cột cũ | `gaze_samples` không có `original_viewport_*`; `view_layouts` không có `coordinate_space`, `visible_rect` |
| Cascade | xoá slide xoá aoi/view/layout/sample; xoá course xoá toàn bộ; xoá user cascade đúng, `courses.created_by` RESTRICT |
| Unique | `users(lower(email))`, `course_visits(enrollment, visit_key) WHERE NOT NULL`, quiz in_progress partial unique, `aois(slide_id, code/label)` |
| Internal metrics | `GET /internal/metrics` hiện trả `200` không auth (khóa hành vi + ghi chú) |

---

## 5. Phần 2 — Eyetracking (UniGaze + MediaPipe + Linear Regression)

### 5.1 Điểm cần khóa

- HTTP session lifecycle: create → calibrate → train → model download/import.
- WS protocol v2: header length + JSON + JPEG; echo field; close code.
- Calibration thật: `numpy.linalg.lstsq` + `.ubj` format `gaze-lr-v2`.
- Throttle FPS: `max(1, int(1000/FPS*0.85))`.
- Giới hạn: 64 điểm, 50 sample/điểm, 5MB upload, 1MB frame, 100 session,
  TTL 1800s.
- Không test `Preprocessor`/`OneEuroFilter` nội bộ; hành vi của chúng được quan
  sát gián tiếp qua HTTP/WS (smoke) và qua kết quả ổn định.

### 5.2 `fast/test_health_ready.py`

| Case | Kỳ vọng |
|---|---|
| `/health` | `200`, có `status`, `pipeline_ready`, `device`, `model`, `precision`, `queue`, `stats`, `sessions` |
| `/ready` khi runtime chưa ready | `503` |
| `/ready` khi ready | `200` |
| Runtime snapshot | `queue.cpu/gpu`, `stats.drop_rate/overload_rate` đúng kiểu số |

### 5.3 `fast/test_session_api.py`

| Case | Input → kỳ vọng |
|---|---|
| Create session | `POST /session` 1..64 điểm unique → `200 {sessionId}` |
| Sai schema | 0 điểm, >64, trùng `id`, x/y ngoài [0,1] → `422` |
| Get status | session mới → `collecting`, `calibrated=false` |
| Unknown session | `404` |
| Calibrate unknown point | `200 {status:"unknown_point"}` |
| Calibrate invalid/no_face | `200` status tương ứng |
| Calibrate pipeline not ready | `503` |
| Calibrate overload | `503 + Retry-After` |
| Calibrate upload lớn | `413` |
| Train thiếu mẫu | `422 {status:"insufficient_samples", detail:{pointId:n}}` |
| Train đủ mẫu | `200 {status:"ok", nSamples:N}`; status session `ready` |
| Download model trước train | `409` |
| Download sau train | `200 application/octet-stream`, `Content-Disposition` `.ubj` |
| Import invalid | `200 {status:"invalid_model"}` (hành vi hiện tại, không 4xx) |
| Import valid | `200 {status:"ready"}`; session calibrated |
| Delete session | `200 {status:"deleted"}`; get lại `404` |
| Session cap | max=1 → tạo thứ 2 `503` (P1) |

### 5.4 `fast/test_calibration_regression.py` — test thật Linear Regression

Fake runtime map bytes ảnh → `(pitch, yaw)` xác định. Không mock `Calibration`.

Kịch bản:

1. Tạo session 4 điểm `(0.1,0.2)`, `(0.9,0.2)`, `(0.1,0.8)`, `(0.9,0.8)`.
2. Với mỗi điểm, gửi 1 ảnh có pitch/yaw tương ứng `(0,0)`, `(1,0)`, `(0,1)`,
   `(1,1)`.
3. `POST /train` → `ok nSamples=4`.
4. Mở WS, gửi từng ảnh, frame đầu tiên (smoother reset) phải trả:
   `x ≈ point.x`, `y ≈ point.y` (sai số 1e-6).
5. `GET /model` → import sang session mới → gửi ảnh `(0.2,0.9)` → cùng kết quả
   như session gốc.
6. Import payload sai format/shape/NaN/format cũ `gaze-lr-v1` → `invalid_model`.

Đây là test hộp đen chứng minh hồi quy tuyến tính + serialize hoạt động, không
phụ thuộc `sklearn`.

### 5.5 `fast/test_stream_ws.py`

| Case | Kỳ vọng |
|---|---|
| Session chưa calibrated | WS close `1008 not_calibrated` |
| Pipeline chưa ready | WS close `1013 pipeline_not_ready` |
| Frame v2 hợp lệ | Nhận `{ok:true,status:"ok",x,y}` + echo `frameId/sequence/captureMonotonicNs/eventTime/presentationId/layoutGeneration` |
| Frame JPEG legacy | Vẫn xử lý, response không có echo field |
| Header sai/không phải v2 | Coi là legacy JPEG; không crash |
| Frame > `MAX_FRAME_BYTES` | Bỏ frame, không phản hồi; frame hợp lệ sau đó vẫn nhận |
| Throttle FPS | 2 frame liên tiếp trong cửa sổ → frame thứ 2 bị bỏ; sau khoảng throttle nhận lại |
| Overload | `{status:"overloaded", suggestedFps:<int>}` |
| No face/invalid image | `{ok:false,status:"no_face"|"invalid_image",error:...}` |
| Stale frame | `{status:"stale",suggestedFps}` (P1, khó deterministic) |

### 5.6 `smoke/test_model_smoke.py` — đúng 1 test ảnh mẫu

- Fixture: `services/gaze/tests/fixtures/face_sample.jpg` (ảnh mặt thật,
  public domain/CC0, ghi nguồn trong `fixtures/README.md`).
- Chạy app thật (lifespan load MediaPipe + UniGaze từ `WEIGHTS_DIR`).
- Assert `/ready` → `200`, `pipeline_ready=true`.
- Tạo session 4 điểm → calibrate cùng ảnh cho 4 điểm (mỗi điểm 1 mẫu) → train
  `ok`.
- Mở WS, gửi ảnh → `status="ok"`, `x/y` hữu hạn trong `[0,1]`.
- Download model → import session mới → stream lại → `ok`.
- Skip nếu thiếu weights/`DEVICE`; fail nếu `REQUIRE_SMOKE=1`.

### 5.7 Cô lập & lệnh chạy

- Fast: không load model; `TestClient(app)` không context manager.
- Fake runtime thay ở `app.api.session.runtime`, reset sau mỗi test.
- Test chạy trong `gaze-test` (build từ target `test`, có `pytest`/`httpx`).
- Smoke mount `gaze-weights`, mặc định `DEVICE=cpu`; override
  `GAZE_TEST_DEVICE=cuda` nếu container test có GPU.
- Lệnh:

```bash
./scripts/test_gaze.sh fast
./scripts/test_gaze.sh smoke
```

---

## 6. Phần 3 — Chatbot (Ingest + Retrieval + Pipeline)

### 6.1 Điểm cần khóa

- Auth nội bộ `X-Chatbot-Token`.
- Ingest theo **slide**, không chunk; skip slide đã `ready`; partial failure.
- Metadata giữ nguyên: course/lesson/slide ID, page number, title, PDF URL.
- Vector dimension 1024; `model_version` ghi từ `EMBEDDING_MODEL_VERSION`.
- Query: access qua backend, retrieval lọc `course_id`, RRF, citation gate,
  SSE event order, fallback không context.
- Không test LangGraph/node; không test `rrf_fuse` trực tiếp.

### 6.2 `fast/test_ingest_api.py`

| Case | Input → kỳ vọng |
|---|---|
| Thiếu/sai token | `401` |
| Slide ID không tồn tại | `404` |
| Happy path 2 slide | `200 {processed:2,failed:0,errors:[]}`; DB `index_status='ready'`, `transcript`, `embedding IS NOT NULL`, `model_version`, `pipeline_version='rag-v2'` |
| Metadata | `v_chatbot_slide_documents` giữ đúng `course_id`, `lesson_id`, `source_page`, `slide_title`, `asset_id` |
| Skip ready | Gọi lại cùng IDs → `processed=0`; VLM/embedding không được gọi |
| Reindex update | Set `index_status='pending'` + đổi transcript/PDF → gọi lại → update cùng row, không tạo slide mới, `updated_at` tăng |
| No chunk | 1 slide dài → đúng 1 row `slides`, 1 document view; không có bảng chunk |
| Response schema | `processed/failed/errors` kiểu số/list, errors là string |
| Request validation | 0 ID / >2000 ID → `422` |
| Concurrent duplicate | 2 request cùng IDs → không nhân đôi xử lý (P1) |

### 6.3 `fast/test_ingest_failures.py`

| Case | Kỳ vọng |
|---|---|
| 1 slide lỗi VLM, 1 slide OK | `processed=1,failed=1`; slide lỗi `failed` + `index_error`; slide OK `ready` |
| Tất cả slide lỗi VLM | `503`; tất cả slide `failed` |
| Trang PDF ngoài range | slide `failed`, lỗi ghi rõ |
| Storage thiếu file | slide `failed`; API trả counts (không 500) |
| Vector dimension mismatch | `Ingestion()` raise RuntimeError khi khởi tạo (P1) |
| DB lỗi | `503` message không lộ credential |
| File PDF hỏng | `failed` cho slide tương ứng |

### 6.4 Retrieval/Vector Search (đã gộp vào `test_query.py`)

Dùng PostgreSQL + pgvector thật, fake embedding.

| Case | Kỳ vọng |
|---|---|
| BM25 hit | transcript chứa từ khóa → document đứng đầu |
| Dense hit | vector gần query (fake map theo từ khóa) → document được chọn |
| RRF | 1 doc hit cả 2 nhánh → điểm cao hơn doc chỉ hit 1 nhánh |
| Course isolation | doc khóa khác không bao giờ xuất hiện trong citations |
| Threshold | vector dưới `RAG_SCORE_THRESHOLD` không vào kết quả |
| `top_k` | không vượt `RAG_TOP_K` |
| Unaccent/FTS | tiếng Việt có dấu/không dấu tìm được (theo `immutable_unaccent`) |
| View filter | slide `index_status != ready` hoặc course draft không được trả |

### 6.5 Query API (đã gộp vào `test_query.py`)

| Case | Input → kỳ vọng |
|---|---|
| Thiếu/sai token | `401` |
| Greeting | "Xin chào" → không retrieval/LLM; `intent=general`, `routes=["general"]` |
| Thanks/help | trả đúng câu cố định |
| Không có docs | fallback "chưa tìm thấy nội dung phù hợp"; `verified=false`, `finish_reason=insufficient_evidence`, citations `[]` |
| Có docs | trả `answer`, `citations` đúng schema; `[n]` khớp 1..len; `verified=true` nếu có citation |
| Citation sai số | non-stream: strip `[99]`, giữ `[1]` |
| Citation gate retry | Lần 1 không citation → retry strict; lần 2 có `[1]` → `verified=true` |
| Citation gate fallback | Cả 2 lần không citation → append "Nguồn tham khảo:", `verified=false`, `finish_reason=citation_failed` |
| Cho phép không citation | câu "không tìm thấy…" → `insufficient_evidence`, không retry vô hạn |
| Query prep lỗi | fallback câu hỏi gốc, vẫn trả lời |
| HyDE | câu ngắn mơ hồ → gọi structured với `hypothetical_answer`; câu có tên riêng → không HyDE |
| History | gửi 30 message; chỉ dùng budget 10 message/16000 ký tự |
| Payload validation | message rỗng/>8000, history >30 → `422` |
| Concurrency | vượt `CHATBOT_MAX_CONCURRENT` → `429 + Retry-After` (P1) |
| LLM lỗi | `503` non-stream; stream `event:error` |

### 6.6 Query stream (đã gộp vào `test_query.py`)

| Case | Kỳ vọng |
|---|---|
| Thứ tự event | `status(rewriting)` → `status(retrieving)` → `citations` → `status(generating)` → `token*` → `status(checking_citations)` → `done` |
| SSE format | `event: <name>\ndata: <json>\n\n`, JSON UTF-8 không escape tiếng Việt |
| Token ghép | ghép token = answer cuối |
| Done schema | `intent`, `verified`, `routes`, `finish_reason`, `citation_count` |
| Không docs | vẫn có `citations` rỗng + `done` |
| LMS thuần | không retrieval; `routes=["lms"]`; render bảng |
| LMS mixed | có `lmsText` + retrieval; `routes=["lms","knowledge"]` |
| Citation gate | token đầu tiên chỉ phát sau khi buffer có citation hợp lệ hoặc hết ngưỡng |
| Client disconnect | không treo semaphore (P1) |

### 6.7 LMS (đã gộp vào `test_query.py`)

| Case | Kỳ vọng |
|---|---|
| Detect | results/assignments/structure/course đúng regex; câu nội dung không bị nhận nhầm |
| Pure vs mixed | "điểm bài tập" pure; "giải thích bài tập" mixed |
| Backend 401/403/404 | `AccessRevoked` → stream `error`, không lộ chi tiết |
| Course mismatch | backend trả course khác → `AccessRevoked` |
| Render | bảng markdown, escape ký tự, ngày GMT+7, remaining seconds |
| Clarification | nhiều quiz trùng tên → trả choices |
| Assignment/results | đúng field `attempt_id`, `score`, `max_score`, `submitted_at` |

### 6.8 `smoke/test_rag_smoke.py` — khép kín

Chạy ngoài process, chỉ dùng HTTP + DB:

1. Login teacher qua backend; tạo course/module/lesson; upload PDF 2 trang
   (tạo bằng `pymupdf`, chứa câu "GazeEdu smoke marker <uuid>").
2. Chờ content-worker tạo slide + embedding-worker ingest xong (poll
   `/teacher/lessons/{id}/slides`, timeout 180s).
3. Publish course; thêm student; login student.
4. `POST /api/courses/{id}/chat/stream` với câu hỏi chứa marker.
5. Assert: có ít nhất 1 `token`, ít nhất 1 citation trỏ đúng slide; lưu
   `chat_messages` (student + assistant).
6. Cleanup: teacher xoá course; assert `v_chatbot_slide_documents` không còn row
   của course; slide cũ ingest lại → `404`.
7. Skip nếu thiếu `CHATBOT_INTERNAL_TOKEN`, `LLM_BASE_URL`, stack/worker.

### 6.9 Cô lập & lệnh chạy

- DB test như backend; `CHATBOT_DATABASE_URL` trỏ DB test.
- `LOCAL_MEDIA_DIR` temp; `STORAGE_PROVIDER=local`.
- Fake provider reset giữa test; đóng pool/retriever/ingestion.
- `Ingestion` được tạo sau khi patch `get_vlm`/`get_embedding`.
- Lệnh:

```bash
./scripts/test_chatbot.sh fast
./scripts/test_chatbot.sh smoke
```

---

## 7. Phần 4 — Frontend E2E smoke (Playwright)

### 7.1 Chiến lược dữ liệu

- Dùng stack thật tại `http://localhost:3000`.
- `./scripts/seed_dev.sh` tạo user seed.
- `scripts/seed_e2e.py` (chạy trước Playwright) tạo **một course published**
  với:
  - 1 module, 1 lesson 2 slide, 1 quiz 1 câu, student đã enroll;
  - `require_calibration=false` để vào thẳng reader;
  - slide `index_status='ready'`, transcript/embedding giả đủ để UI hiển thị;
  - 1 visit + 2 content_view + layout + 20 gaze sample + metrics/heatmap/
    `aoi_stats` đã set sẵn (`analysis_status='ready'`,
    `analysis_version='gaze-metrics-v8'`).
- Ghi ID vào `frontend/e2e/.fixtures.json` (gitignored).
- Seed idempotent: xoá course có title prefix `E2E ` trước khi tạo.
- Flow giáo viên tạo course riêng với prefix `E2E Draft `; teardown xoá qua API.

### 7.2 Flow 1 — `auth-roles.spec.ts`

1. Mở `/` → thấy link/CTA "Đăng nhập".
2. Mở `/student` khi chưa đăng nhập → redirect `/account/login?next=/student`.
3. Login student (`student@school.edu.vn` / `Password123!`) → URL `/student`,
   heading "Khóa học của tôi"; thấy course seed.
4. Logout (menu tài khoản) → quay lại login; mở `/student` lại → redirect.
5. Login teacher → `/teacher`, heading "Khóa học"; thấy danh sách khóa.
6. Login admin → `/admin`, heading "Nâng cấp giáo viên".

Không assert nội dung nhạy cảm trong token/cookie.

### 7.3 Flow 2 — `teacher-content.spec.ts`

1. Login teacher → `/teacher` → "Tạo khóa học".
2. Nhập `#new-course-title` = `E2E Draft <timestamp>`, mô tả; bấm "Tạo khóa học".
3. Ở workspace tab "Nội dung": bấm "Thêm chương"; đổi tên chương inline.
4. Bấm "Thêm nội dung" → "Bài giảng (PDF)"; đổi tên bài.
5. Bấm "Xuất bản" → dialog "Kiểm tra trước khi xuất bản" hiển thị
   "Bài giảng chưa có tài liệu PDF — không thể xuất bản"; đóng dialog.
6. Tab "Thông tin": tắt "Bắt buộc hiệu chỉnh"; chờ message
   "Đã tắt bắt buộc hiệu chỉnh."
7. Tab "Học viên": mở "Thêm học viên", tìm mã SV seed, thêm; thấy row student.
8. Teardown: gọi API xoá course vừa tạo.

### 7.4 Flow 3 — `student-learning-quiz.spec.ts`

1. Login student → mở course seed.
2. Reader hiển thị slide 1/2; bấm "Sau" → 1/2 → 2/2; bấm "Trước" → 1/2.
3. Mở mục lục (mobile: "Mở mục lục"), chọn bài quiz.
4. Quiz auto-start attempt; chọn đáp án đúng; bấm "Nộp bài"; xác nhận.
5. Màn hình review hiển thị "Đáp án đúng", điểm `1/1`, nút "Làm lại bài tập?"
   (seed `allowRetry=true`).
6. Bấm "Làm lại" → quay lại câu hỏi, attempt mới.
7. DB (qua API teacher analytics): có ít nhất 1 visit, 2 content view, quiz
   attempt `submitted` + `in_progress` mới.

### 7.5 Flow 4 — `teacher-analytics.spec.ts`

1. Login teacher → mở course seed → tab "Trực quan hoá".
2. Replay: chọn student/ca seed (hoặc deep link
   `?tab=visualization&mode=replay&visitId=<id>`); thấy "2 lượt xem",
   "20 gaze", timeline, sample đầu; bấm play → timeline tiến.
3. Bật/tắt "Chỉ lượt >= ngưỡng" (nếu có) → số view đổi theo seed.
4. Chuyển "Tổng hợp": thấy card tổng gaze, bảng AOI có nhãn seed, heatmap
   24×24 render (aria-label "Lưới heatmap 24x24"), số mẫu trong slide = 20.
5. Đổi filter "Bài giảng"/"Bài tập" → dữ liệu lọc đúng (không crash).

### 7.6 Flow 5 — `student-chat.spec.ts` (optional, smoke thật)

Gate `E2E_CHAT=1`; cần chatbot + LLM thật và slide đã ingest thật. Khi bật cờ
này, `seed_e2e.py --real-ingest` upload PDF và chờ worker ingest xong; không
dùng embedding giả của seed UI (embedding giả có thể không retrieval ra citation).

1. Login student → mở course seed → mở reader.
2. Bấm "Mở trợ lý học tập"; panel "Trợ lý học tập" hiện.
3. Nhập câu hỏi về marker trong slide; bấm "Gửi câu hỏi".
4. Thấy token stream dần; kết thúc có ít nhất 1 citation; bấm citation →
   nhảy đúng slide (reader mode).
5. Đóng/mở lại panel → lịch sử còn; đổi tên phiên; xoá phiên → biến mất.
6. Nếu `allowChatbot=false` và có quiz đang mở → panel báo khóa, input disabled.

### 7.7 Cấu hình & lệnh

`playwright.config.ts`:

- `testDir: "./e2e"`, `fullyParallel: false`, 1 worker.
- `baseURL: E2E_BASE_URL || http://localhost:3000`.
- `trace: retain-on-failure`, screenshot only-on-failure.
- `webServer` không dùng; yêu cầu stack đang chạy.

```bash
./scripts/e2e.sh                 # seed + Playwright (4 flow)
E2E_CHAT=1 ./scripts/e2e.sh      # thêm flow chat
npx playwright test e2e/auth-roles.spec.ts
```

---

## 8. CI gate và lịch chạy

| Gate | Lệnh | Bắt buộc |
|---|---|---|
| Mỗi lần sửa | `make check` (ruff/eslint/typecheck) | Có |
| Trước commit | `./scripts/test_fast.sh` | Có |
| Trước PR | `make check && ./scripts/test_fast.sh` | Có |
| Trước merge | `./scripts/test_smoke.sh` (gaze + chatbot + E2E) | Có nếu môi trường có GPU/LLM |
| Release | `make check-full && ./scripts/test_fast.sh && ./scripts/test_smoke.sh` | Có |

Không đưa E2E vào `fast`; không đưa smoke vào `make check`.

---

## 9. Dependency & test seam cần duyệt

### 9.1 Dev dependencies (không thêm runtime dep)

| Nơi | Package | Mục đích |
|---|---|---|
| `backend/requirements-dev.txt` | `pytest`, `pytest-asyncio`, `asgi-lifespan`, `respx` | API/DB/SSE test |
| `services/chatbot/requirements-dev.txt` | `pytest`, `pytest-asyncio`, `asgi-lifespan` | API/DB/SSE test |
| `services/gaze/requirements-dev.txt` | `pytest`, `httpx` | HTTP/WS test |
| `frontend/package.json` | `@playwright/test` | E2E |

Pin version cụ thể khi cài (theo version đã kiểm tra trong venv), không dùng
`>=`. Không thêm `pytest-xdist`, `fakeredis`, `freezegun`, `testcontainers` ở
giai đoạn đầu.

### 9.2 Test seam (thay đổi nhỏ, không đổi hành vi)

1. **Chatbot provider injection (khuyến nghị)**:
   `Ingestion.__init__(self, *, vlm=None, embedding=None, storage=None)` với
   default giữ nguyên. Cho phép test truyền fake mà không monkeypatch private.
   Nếu không muốn sửa code, dùng monkeypatch factory ở biên.
2. **Worker one-shot (khuyến nghị)**:
   đọc env `WORKER_MAX_ITERATIONS` trong `run_worker_loop` để chạy
   `python -m app.worker` một lượt. Nếu không, dùng adapter gọi entrypoint.
3. **E2E seed script**: chỉ thêm file `scripts/seed_e2e.py`, không sửa API.

Các thay đổi này cần được duyệt trước khi triển khai; kế hoạch này không tự
thực hiện.

---

## 10. Rủi ro & ngoài phạm vi

### 10.1 Rủi ro

- **Smoke LLM không deterministic**: chỉ assert cấu trúc/citation, không assert
  nội dung câu trả lời.
- **Smoke cần GPU/weights**: CI không GPU phải skip có kiểm soát; release phải
  chạy thủ công trên máy có GPU.
- **E2E phụ thuộc seed**: seed lệch → fail; seed script phải idempotent và
  log ID rõ.
- **Không có testid**: đổi label/text UI sẽ làm E2E fail; đó là chấp nhận vì
  label là hợp đồng người dùng.
- **Redis dùng chung**: phải FLUSHDB 15 trước mỗi test; không trỏ vào DB thật.
- **Advisory lock/time**: test chạy tuần tự; không parallel giai đoạn đầu.
- **Ingest partial failure**: semantics "chỉ 503 khi tất cả VLM lỗi" dễ bị vô
  tình đổi khi refactor; test phải khóa rõ.

### 10.2 Ngoài phạm vi

- Unit test UI chi tiết (Vitest) — theo yêu cầu.
- Test load/performance, benchmark query count.
- Test model accuracy/quality (chỉ smoke “chạy được”).
- Test OAuth/Microsoft Entra (không còn trong hệ thống).
- Test admin DB UI chi tiết; chỉ test API đọc-only + quyền.
- LangGraph/node graph (không còn trong code).

---

## 11. Thứ tự thực hiện & tiêu chí hoàn thành

### Giai đoạn 1 — Hạ tầng (0.5 ngày)

- Thêm dev deps, `pytest.ini`, `playwright.config.ts`.
- `scripts/test_backend.sh`, `test_gaze.sh`, `test_chatbot.sh`, `test_fast.sh`.
- `conftest.py`, DB truncate, Redis flush, fake providers.
- Tiêu chí: `pytest -m fast` chạy 0 test nhưng collect thành công; DB test
  migrate generation 13; Redis ping OK.

### Giai đoạn 2 — Backend P0 (1.5 ngày)

- Auth, authz matrix, courses/publish, visits/sessions, presentations/gaze,
  quiz.
- Tiêu chí: ~70 case P0 pass; `./scripts/test_backend.sh` < 3 phút.

### Giai đoạn 3 — Backend P1 + analytics (1 ngày)

- AOI, metrics worker, analytics API, chat proxy, maintenance, schema.
- Tiêu chí: ~110 case pass; không test nào gọi hàm private.

### Giai đoạn 4 — Gaze (1 ngày)

- Fast API/WS + calibration regression.
- Smoke ảnh mẫu (chạy được trên máy GPU).
- Tiêu chí: fast pass không cần model; smoke pass với weights thật.

### Giai đoạn 5 — Chatbot (1.5 ngày)

- Ingest happy/failure/idempotent/reindex.
- Retrieval thật + query/SSE + LMS.
- Smoke khép kín ingest → query → cleanup.
- Tiêu chí: fast pass với fake model; smoke pass với stack + LLM thật.

### Giai đoạn 6 — Frontend E2E (1 ngày)

- Seed script + 4 flow bắt buộc + flow chat optional.
- Tiêu chí: `./scripts/e2e.sh` pass 2 lần liên tiếp trên stack sạch; không flaky.

### Giai đoạn 7 — Ổn định (0.5 ngày)

- Chạy lặp 3 lần, kiểm tra thứ tự test, cleanup, log.
- Cập nhật `AGENTS.md` mục 2 (lệnh test) và checklist trước khi kết thúc.
- Tiêu chí: `fast` < 3 phút, `smoke` < 10 phút, không rò dữ liệu giữa test.

---

## 12. Bảng tổng hợp file ↔ case ↔ lệnh

| Khu vực | File chính | Số case dự kiến | Lệnh |
|---|---|---:|---|
| Backend auth | `tests/fast/test_auth.py` | 15 | `./scripts/test_backend.sh` |
| Backend content/publish | `test_courses_content.py`, `test_publish.py` | 22 | nt |
| Backend visit/session | `test_visits_sessions.py` | 14 | nt |
| Backend gaze | `test_presentations_layouts.py`, `test_gaze_ingest.py` | 22 | nt |
| Backend quiz | `test_quiz.py` | 14 | nt |
| Backend AOI | `test_aoi_editor.py` | 11 | nt |
| Backend analytics | `test_metrics.py`, `test_analytics.py` | 10 | nt |
| Backend chat proxy | `test_chat_proxy.py` | 10 | nt |
| Backend maintenance/schema | `test_maintenance.py`, `test_schema_contract.py` | 12 | nt |
| Gaze fast | 3 file | 20 | `./scripts/test_gaze.sh fast` |
| Gaze smoke | 1 file | 1 | `./scripts/test_gaze.sh smoke` |
| Chatbot ingest | 2 file | 15 | `./scripts/test_chatbot.sh fast` |
| Chatbot retrieval/query | 3 file | 25 | nt |
| Chatbot smoke | 1 file | 1 | `./scripts/test_chatbot.sh smoke` |
| Frontend E2E | 5 file | 5 flow | `./scripts/e2e.sh` |

Đã triển khai: **123 case fast** (79 backend + 22 gaze + 22 chatbot), **3 smoke
test** (gaze model, chatbot RAG, backend/LLM E2E qua Playwright) và **9 flow
Playwright** (1 flow chat chỉ chạy khi `E2E_CHAT=1`).
