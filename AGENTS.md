# AGENTS.md — GazeEdu / EyeLearning

> Trạng thái: **schema generation 13**, **24 bảng lõi**, không versioning nội dung.
> Tài liệu phản ánh code hiện tại ngày 2026-11-16.

## 0. Tóm tắt

GazeEdu là nền tảng học trực tuyến có theo dõi hướng nhìn:

- Giáo viên tạo khóa → chương → bài giảng/bài tập → upload PDF/PPTX/PPT/ODP.
- Học viên đăng nhập bằng email trường + OTP, học slide PDF, làm quiz, chat với trợ lý RAG.
- Webcam gửi gaze 12 FPS qua WebSocket tới service `gaze`; frontend gom batch gửi backend.
- Backend lưu gaze thô; worker quy đổi sang tọa độ slide, gắn `aoi_label` duy nhất và tính metrics.
- Giáo viên xem tỷ lệ quan sát, xuất JSONL phẳng để phân tích.

Không còn `course_versions`, `lesson_versions`, `slide_versions`,
`course_version_items`, `slide_documents`, `gaze_batches`, `aoi_sets`,
`aoi_hits`, `analysis_runs` hay `presentation_metrics`.

## 1. Công nghệ

| Lớp | Công nghệ |
|---|---|
| Frontend | Next.js 16 App Router, React 19, TypeScript, Tailwind 4, TanStack Query |
| Backend | FastAPI, Python 3.12, SQLAlchemy async, Pydantic 2 |
| DB | PostgreSQL 16 + pgvector |
| Gaze | MediaPipe + UniGaze, PyTorch CUDA, WebSocket |
| Chatbot | FastAPI, hybrid FTS + pgvector, Qwen qua NEU API, embedding CPU |
| Hạ tầng | Docker Compose local, nginx, Redis tùy chọn, SMTP gửi OTP |

## 2. Kiến trúc

```text
Browser → nginx :3000
  /api, /media → backend :8001
  /gaze        → gaze :8000
  /*           → frontend :3000

backend → PostgreSQL
backend → SMTP (OTP đăng nhập sinh viên)
backend → chatbot :8000 (internal token)
worker  → background_jobs (analyze_lesson)
content-worker → background_jobs (import_slides)
embedding-worker → background_jobs (index_slides)
```

Volume chính: `pgdata`, `backend-media`, `gaze-weights`, `chatbot-weights`.
`docker compose down -v` xóa toàn bộ DB/media/weights; chỉ dùng khi reset sạch.

## 3. Mô hình dữ liệu hiện tại

24 bảng lõi, chia 8 nhóm:

| Nhóm | Bảng |
|---|---|
| Danh tính | `users`, `auth_sessions`, `email_otps`, `student_profiles`, `teacher_profiles` |
| Khóa học | `courses`, `course_teachers`, `enrollments`, `course_visits`, `media_assets` |
| Nội dung | `course_modules`, `lessons`, `slides` |
| Job | `background_jobs` |
| Quiz | `quiz_attempts` |
| Gaze/AOI | `gaze_calibrations`, `learning_sessions`, `content_views`, `view_layouts`, `gaze_samples`, `aois` |
| Chat | `chat_sessions`, `chat_messages` |
| Metadata | `app_metadata` |

Xem từ điển cột/ERD trong [`DB.md`](DB.md).

### Quan hệ nội dung

```text
courses
  └── course_modules
        └── lessons
              ├── slides → aois
              └── quiz_attempts

enrollments
  └── course_visits
        └── learning_sessions
              └── content_views
                    ├── view_layouts
                    └── gaze_samples
```

- Mỗi user có **một role**: `admin | teacher | student`.
- Không có versioning. Sửa nội dung đã publish áp dụng ngay cho học viên.
- Publish chỉ validate rồi đổi `courses.status = 'published'`.
- Replace PDF của bài = xóa slide cũ + cascade gaze/AOI của các slide đó.
- Quiz attempt lưu `quiz_snapshot` để xem lại đúng đề lúc làm.

## 4. API contract

Frontend và backend dùng thống nhất ID hiện hành, không còn alias `*VersionId`:

| Field/endpoint | Giá trị |
|---|---|
| `slideId` | `slides.id` |
| `lessonId` | `lessons.id` |
| `presentationId` | `content_views.id` |
| `layoutId` | `view_layouts.id` |
| `GET /api/aois?slideId=...` | AOI hiện hành của slide |
| `GET /api/lessons/{lessonId}/quiz` | quiz config của bài tập |
| `PATCH /teacher/lessons/{lessonId}/quiz` | cập nhật quiz config |
| `POST /api/course-visits` | tạo ca học khi vào khóa |
| `GET /teacher/courses/{courseId}/visits` | tất cả ca của khóa |
| `GET /teacher/visits/{visitId}/gaze` | gaze/AOI của một ca |
| `GET /teacher/visits/{visitId}/replay` | layout + AOI + thống kê để phát lại ca |
| `GET /teacher/visits/{visitId}/samples` | sample replay, phân trang keyset |
| `POST /teacher/courses/{courseId}/analytics/aoi-summary` | tổng hợp thời lượng AOI |
| `POST /teacher/courses/{courseId}/analytics/heatmap` | heatmap 24×24 theo slide |
| `POST /api/auth/otp/request` | gửi OTP tới email sinh viên |
| `POST /api/auth/otp/verify` | xác nhận OTP, cấp token/cookie |

`presentationId` là tên domain cho một lượt xem slide/quiz và cũng là metadata
trong gaze protocol; không phải bảng version.

Đăng nhập sinh viên dùng OTP qua SMTP, không cần Microsoft Entra admin.
Email hợp lệ mặc định: `^\d{8}@st\.neu\.edu\.vn$`.

## 5. Luồng giáo viên

1. Tạo khóa: `courses.status='draft'`.
2. Tạo chương trong `course_modules`.
3. Tạo bài trong `lessons`, gắn trực tiếp `module_id` + `position`.
4. Upload slide:
   - API lưu file staging, tạo `background_jobs(kind='import_slides')`.
   - content-worker convert PDF, tạo `media_assets`, thay toàn bộ `slides` của bài.
   - slide mới có `index_status='pending'`; enqueue `index_slides`.
5. Soạn quiz trong `lessons.quiz_config JSONB`.
6. AOI slide do giáo viên vẽ tay trong “Vùng phân tích” và lưu trực tiếp trong
   `aois`; nhãn do giáo viên đặt dạng `AOI_THANHCHAT`, `AOI_BANGBIEU`…
   Không còn sinh gợi ý vùng từ PDF. AOI UI dùng `ui_schema='reader-v1'`.
7. Tab **Trực quan hoá**:
   - **Xem lại ca học** dựng lại `view_layouts` + slide PDF + gaze dot; vùng
     AOI khớp `gaze_samples.aoi_label` sáng lên.
   - **Tổng hợp** đọc `content_views.aoi_stats`, lọc theo ca/học viên/bài/ngày
     và vẽ biểu đồ thời lượng, cơ cấu, xu hướng, heatmap 24×24.
   - Nút “Xem lại” trong sheet học viên mở đúng ca; cảnh báo
     `SLIDE_NO_LABEL`/`UI_NO_LABEL` mở đúng slide trong tab Vùng phân tích.
8. Publish:
   - Kiểm tra có chương/bài, bài giảng có slide, mọi slide `index_status='ready'`,
     quiz có câu hỏi hợp lệ.
   - Đổi `courses.status='published'`; không tạo snapshot.

Các endpoint teacher nằm dưới backend `/teacher/...`. Browser gọi
`/api/teacher/...`; nginx/Next bỏ prefix `/api`.

## 6. Luồng học viên và gaze

1. Đăng nhập bằng email trường + OTP → chọn khóa đã enroll.
2. Nếu `courses.require_calibration=true`: calibration 25 điểm, lưu
   `gaze_calibrations`.
3. Mở trang khóa: tạo `course_visits` (mỗi lần vào khóa là một ca).
4. Mở từng bài: tạo `learning_sessions` với `course_visit_id` của ca hiện tại.
5. Mỗi slide/quiz: tạo `content_views(session_id, slide_id, sequence_no)`.
   - Frontend gửi `clientPresentationId` (UUID) cho mỗi lần vào slide; retry
     cùng UUID là idempotent, UUID mới luôn tạo lượt xem mới kể cả khi quay
     lại slide cũ.
   - Server cấp `sequence_no = max + 1` trong session; không phụ thuộc bộ đếm
     của client để tránh ghi đè sau reload.
   - Tab Trực quan hoá hiển thị **tất cả** lượt xem, kể cả lượt ngắn hơn
     `CONTENT_VIEW_MIN_DWELL_MS` và lượt không có sample gaze. Ngưỡng này chỉ
     phân loại `counted` và làm bộ lọc tùy chọn, không ẩn mặc định.
   - Kết thúc session/visit đóng `ended_at` của mọi content view đang mở.
6. Resize/mở chat/đổi layout: tạo `view_layouts` trong hệ toạ độ viewport
   hiện tại:
   - `slide_rect`: vùng PDF trong viewport hiện tại.
   - `elements`: mảng rect UI trong viewport hiện tại.
   - Gaze được quy đổi từ viewport lúc calibration sang viewport hiện tại khi
     cửa sổ resize/move. Zoom/fullscreen bị display guard phát hiện và tạm
     dừng ghi gaze.
7. Khung reader cố định: slide co vừa vùng nội dung, không cuộn dọc; nút
   Trước/Sau là footer ngoài slide. Quiz chỉ cuộn nội bộ danh sách đáp án
   (và danh sách review), không cuộn toàn khung.
8. Gaze batch:
   - POST `/api/learning-sessions/{id}/gaze-batches`.
   - Mỗi sample ghi trực tiếp vào `gaze_samples`.
   - `viewport_x/y`: toạ độ viewport hiện tại, đã quy đổi từ calibration.
   - Unique `(content_view_id, client_batch_id, sequence)` chống trùng.
9. Đóng phiên: enqueue `background_jobs(kind='analyze_lesson')`.
10. Worker phân tích:
   - `viewport_x/y` → `slide_x/y` bằng `view_layouts.slide_rect`.
   - nếu điểm nằm trong slide `[0,1]`: chọn **một** leaf slide theo
     `custom > text > table > image > drawing > system`, cùng hạng thì diện
     tích nhỏ hơn; nhãn là `SLIDE_<aois.label>` (ví dụ `SLIDE_AOI_1`,
     `SLIDE_AOI_THANHCHAT`).
   - trong slide nhưng ngoài mọi leaf: `SLIDE_NO_LABEL`.
   - ngoài slide (kể cả quiz/layout thiếu): chọn **một** UI AOI, ưu tiên
     `custom` rồi diện tích nhỏ hơn; nhãn là `aois.name` (ví dụ
     `Mục lục`, `Thanh chat`, `Nút gửi`).
   - ngoài slide nhưng ngoài mọi UI AOI: `UI_NO_LABEL`.
   - mỗi sample chỉ có **một** `aoi_label`; không trộn nhãn slide + UI, không
     cộng container. Không còn `aoi_codes`.
   - cập nhật metrics vào `content_views`, gồm `heatmap_grid` và `aoi_stats`
     (`{label: {ms, samples}}`) cho dashboard Trực quan hoá.

Sửa AOI không xóa gaze thô; worker chỉ tính lại `slide_x/y`, `aoi_label`,
metrics và `aoi_stats`. Nhãn slide do giáo viên đặt trong `aois.label`
(dạng `AOI_...`).

## 7. Xóa dữ liệu

| Xóa | Cascade |
|---|---|
| Slide | AOI, content views, layout, gaze, metrics của slide |
| Bài học | Slide và toàn bộ session/view/gaze/quiz attempt/chat/job của bài |
| Chương | Toàn bộ bài trong chương |
| Khóa học | Chương/bài/slide/enrollment/course visit/session/gaze/chat/media/job |

File local/R2 được dọn theo prefix/object key sau thao tác DB. Không còn
trigger bất biến hay cờ `app.allow_course_delete`.

## 8. Chatbot / RAG

- Index nằm trực tiếp trên `slides` (`transcript`, `embedding`, `content_tsv`,
  `index_status`, `index_error`).
- Backend enqueue `index_slides`; worker gọi chatbot `/ingest/slides` theo batch.
- Chatbot chỉ được role DB đọc view outline và UPDATE các cột index của `slides`.
- Retrieval lọc theo `course_id`; không còn version filter.
- Citation mới dùng `courseId/lessonId/slideId/assetId/pageNumber`; response vẫn
  kèm alias cũ cho frontend.
- Không đọc được users, quiz attempts, chat của user khác.

## 9. Database/migration

- Baseline: `001_baseline.sql` (generation 12). Nâng cấp hiện hành:
  - `002_email_otp.sql`: `email_otps`, `users.email_verified_at`, bỏ
    `oauth_accounts`, nâng `schema_generation='13'`.
  - `003_aoi_single_label.sql`: bỏ `gaze_samples.aoi_codes` và
    `slides.aoi_suggestions`.
  - `004_content_view_aoi_stats.sql`: thêm `content_views.aoi_stats` JSONB
    (dữ liệu dẫn xuất cho dashboard Trực quan hoá; worker `gaze-metrics-v6`
    ghi lại, có thể tái tạo bằng phân tích lại).
  - `005_current_viewport_only.sql`: chuyển `view_layouts` cũ từ
    `original-v1` sang viewport hiện tại, bỏ `coordinate_space`,
    `visible_rect`, `gaze_samples.original_viewport_x/y`. Giữ generation 13.
- DB generation cũ không migrate tại chỗ nếu chưa có `schema_migrations`; phải backup rồi reset có guard:
  ```bash
  ./scripts/backup.sh
  ./scripts/reset_db.sh --apply --database eyetracking \
    --confirm-reset eyetracking --seed-dev
  ```
- Backend fail-fast nếu `app_metadata.schema_generation != '13'`.
- `schema_migrations`, `app_metadata` không tính vào 24 bảng lõi.
- Role `chatbot_reader` và `admin_reader` được tạo bởi `db/migrate.sh`.
  `admin_reader` không đọc `auth_sessions`, `email_otps`; chatbot role cũng
  không đọc `email_otps`.

## 10. Chạy và kiểm tra

```bash
cp .env.example .env
docker compose up -d --build
./scripts/seed_dev.sh

make check
make test-backend
make test-frontend
```

Tài khoản seed (mật khẩu `Password123!`):

| Email | Role |
|---|---|
| admin@school.edu.vn | admin |
| teacher@school.edu.vn | teacher |
| student@school.edu.vn | student |

Đăng nhập sinh viên NEU dùng OTP qua SMTP. Cấu hình tối thiểu trong `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASS=...
SMTP_FROM=              # trống → dùng SMTP_USER
SMTP_REPLY_TO=          # trống → dùng địa chỉ From
OTP_TTL_SECONDS=900
OTP_ALLOWED_DOMAINS=st.neu.edu.vn
OTP_STUDENT_ID_PATTERN=^\d{8}$
```

Không cần `MICROSOFT_CLIENT_ID/SECRET/TENANT_ID`.

Gmail cá nhân gửi tới `st.neu.edu.vn` (Microsoft 365) có thể bị chuyển vào
Thư rác/Quarantine ở lần gửi đầu. Email OTP không chèn link để giảm tín hiệu
phishing; nếu triển khai thật nên dùng SMTP relay/transactional provider với
domain gửi đã có SPF/DKIM/DMARC. Lỗi SMTP `550 5.4.1 Recipient address rejected:
Access denied` nghĩa là địa chỉ sinh viên không tồn tại trong tenant, không
phải lỗi cấu hình.

### 10.1 Production qua Portainer

- Stack production: `deploy/portainer/docker-compose.yml`; chỉ pull image từ
  GHCR, **không** build trên server.
- `cloudflared` nằm trong stack, public hostname trỏ `http://nginx:80`.
- Nginx phải giữ `real_ip_header CF-Connecting-IP` và forward
  `X-Forwarded-Proto` từ Cloudflare; nếu không rate limit/OTP sẽ tính chung IP
  cloudflared.
- Không commit `deploy/portainer/stack.env`, `.env`, tunnel token, backup.
- Hướng dẫn đầy đủ: `deploy/portainer/README.md`.

## 11. Lưu ý cho coding agent

- Không thêm lại bảng `*_versions`, `slides_documents`, `gaze_batches`,
  `aoi_sets`, `aoi_hits`, `presentation_metrics`, `oauth_accounts`.
- Tên bảng/cột mới là nguồn sự thật; alias cũ chỉ ở API/frontend.
- `gaze_samples.viewport_x/y` chuẩn hóa `[0,1]` theo viewport tại thời điểm
  ghi và là nguồn duy nhất cho mapping AOI. Không hardcode pixel.
- `view_layouts.slide_rect/elements` luôn ở hệ toạ độ viewport hiện tại;
  không còn `original-v1`, `visible_rect` hay `original_viewport_x/y`.
- Gaze lưu thô bất biến; `slide_x/y`, `aoi_label`, metrics là dẫn xuất, được
  phép tính lại.
- Nhãn duy nhất: slide dùng `SLIDE_<aois.label>`/`SLIDE_NO_LABEL`; UI dùng tên
  AOI/`UI_NO_LABEL`. Không lưu nhiều AOI chồng nhau trong `aoi_label`.
- `aois.label` do giáo viên đặt, regex `^AOI_[A-Z0-9_]{1,60}$`, unique trong
  slide. Ví dụ `AOI_THANHCHAT` → nhãn gaze `SLIDE_AOI_THANHCHAT`.
- Backend không dùng `pymupdf`; validate PDF bằng `pypdf`. Chatbot vẫn dùng
  `pymupdf` để render slide cho RAG.
- Trang calibration và reader có display guard: phát hiện zoom/fullscreen, hiện
  overlay và tạm dừng ghi gaze. Resize cửa sổ cũng tạm dừng ngay để snapshot
  layout mới sẵn sàng trước khi ghi tiếp. Trình duyệt không cho chặn tuyệt đối
  F11/page zoom; guard là best-effort + không ghi dữ liệu khi trạng thái sai.
- “Ca học” là `course_visits`, không phải `learning_sessions` (mỗi lesson một session).
- `CONTENT_VIEW_MIN_DWELL_MS` (mặc định 1000) chỉ dùng để tính
  `dwell_ms/counted` và bộ lọc “Chỉ lượt >= ngưỡng”. Mặc định Replay/Tổng hợp
  vẫn trả và hiển thị mọi lượt xem, kể cả lượt 0 sample hoặc thiếu layout.
- `scripts/reset_gaze_data.sh` chỉ xoá lịch sử gaze (`course_visits` cascade)
  và job analyze đang chờ; không xoá nội dung khóa học/AOI/người dùng.
- Sửa cascade/FK phải chạy test `test_simplified_schema.py`.
- Document DB mới trong `DB.md`, không dựa vào thiết kế generation 9 cũ.
