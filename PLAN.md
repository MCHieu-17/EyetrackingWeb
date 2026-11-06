# PLAN.md — Tái cấu trúc LMS, Eye Tracking và baseline database

**Trạng thái:** Phase 0–6 đã triển khai trên nhánh `refactor/lms-v2`; development DB đã reset có guard và stack mới đang chạy.

**Phạm vi:** Thiết kế lại database và các consumer liên quan; reset riêng database development đã xác minh. Không giữ dữ liệu cũ, không backfill, không duy trì API/schema tương thích ngược.

**Hai quyết định đã được xác nhận:**

- Xuất bản thay đổi ở cấp **toàn khóa học**.
- Lưu **mọi kết quả inference**, kể cả trạng thái không nhận diện được khuôn mặt; chỉ giảm mẫu khi hiển thị hoặc phân tích.

**Cơ sở phân tích:** Đã khảo sát source, migrations và catalog PostgreSQL bằng truy vấn read-only. Tài liệu này lưu toàn bộ thiết kế đã thống nhất và chi tiết hóa các phase; chưa triển khai code, migration hoặc reset database. Thông tin môi trường bên dưới là kết quả khảo sát ngày 06/11/2026 và phải được xác minh lại trước khi reset.

## 1. Hiện trạng đã xác minh và hướng xử lý

### 1.1. Môi trường

- Repository tại commit `15fae94`.
- Docker sử dụng socket local `unix:///var/run/docker.sock`.
- Compose project `eyelearning`, cấu hình thuộc repository hiện tại.
- PostgreSQL chạy trong `eyetracking-postgres`, phiên bản **16.15**, pgvector **0.8.7**.
- Backend kết nối service `postgres`, database **`eyetracking`**.
- Database đã áp **28 migrations**.
- Cùng PostgreSQL còn có `ci_fresh`, `ci_up`, `eyetracking_fresh`, `eyetracking_test` và `postgres`. Những database này **không nằm trong phạm vi reset**.
- Backend hiện có cấu hình **R2**. Quyền reset database development không được hiểu thành quyền xóa bucket hoặc file R2.

### 1.2. Những vấn đề cần giải quyết

| Khu vực | Bằng chứng trong code/schema hiện tại | Quyết định |
|---|---|---|
| Nội dung | Course/module/lesson/slide được sửa trực tiếp; publish chủ yếu đổi status | Tách identity khỏi phiên bản; published content bất biến |
| Xóa/thay PDF | DELETE bài/slide và thay PDF kích hoạt cascade; raw gaze có FK `SET NULL`; file cũ bị cleanup | Gỡ nội dung khỏi bản phát hành mới; giữ nội dung và asset lịch sử |
| Quiz | Đề đang dùng có thể bị ghi đè; submit chấm đề hiện tại; retry xóa attempt cũ | Đề gắn lesson version; mỗi lượt làm là bản ghi riêng |
| Phiên học | Mở lại session đã đóng, cập nhật viewport vào session cũ | Session có ranh giới rõ và context cố định |
| Calibration | Ghi đè model/MAE của cùng user-device | Lưu từng calibration bất biến |
| Gaze | Ghi song song raw và events với sampling khác nhau; metadata viewport lặp trên mỗi mẫu | Một bảng gaze gốc; metadata cố định đặt tại calibration/session/batch |
| Thu mẫu | Timestamp lấy lúc nhận inference; context lấy lúc flush; xóa buffer trước ACK | Gắn context lúc capture; frame ID; queue có ACK và idempotency |
| AOI | Hai hệ bảng AOI; `aoi_regions`/`aoi_dwell_stats` không có luồng nghiệp vụ đang sử dụng | Một mô hình AOI versioned hỗ trợ slide và giao diện |
| Rebuild AOI | DELETE theo toàn session nhưng INSERT có lọc thời gian | Mỗi lần phân tích có scope, watermark và kết quả riêng |
| Layout | Debounce có thể bị gaze-dot làm reset liên tục; key không chứa session; response cũ có thể bật ready | Snapshot theo session/presentation/generation; loại overlay khỏi observer |
| Analytics | Nhiều bảng tổng hợp chồng chéo; đọc toàn bộ events rồi downsample trong RAM | Tổng hợp từ một nguồn gaze; projection theo presentation, truy vấn có giới hạn thời gian |
| Rate limit | Gaze giới hạn 60 request/phút/IP, reader gửi khoảng 40 request/phút | Giới hạn theo user/session; tránh chặn cả lớp cùng NAT |
| Chat/RAG | Query theo cây hiện tại; các query quiz giả định mỗi người chỉ có một attempt | Lọc theo course version và attempt cụ thể |
| Migrations/test | Chuỗi tạo–sửa–xóa–tạo lại bảng; fixture có parser SQL và tự replay migrations | Một baseline sạch; một runner chung cho dev/test/CI |

Nguồn chính: [luồng nội dung](</home/hieu/Documents/NCKH Eyetracking/EyeLearning/backend/app/api/routes/lessons.py>), [luồng gaze](</home/hieu/Documents/NCKH Eyetracking/EyeLearning/backend/app/api/routes/gaze.py>), [rebuild AOI](</home/hieu/Documents/NCKH Eyetracking/EyeLearning/backend/app/services/aoi_hits.py>).

Khóa ngoại thực tế đã xác nhận `gaze_events → lesson_contents` và `quiz_assignments → lessons` dùng `CASCADE`, khác một số khai báo ORM hiện tại. Baseline mới phải loại bỏ sự lệch này.

## 2. Kiến trúc được chọn

### 2.1. So sánh phương án

| Phương án | Trade-off | Lựa chọn |
|---|---|---|
| Chỉ soft delete | Giữ được dòng bị xóa nhưng không giữ nội dung trước khi bị sửa | Không đủ |
| Cấm sửa khi đã có gaze | Đơn giản nhưng không đáp ứng nghiệp vụ | Không chọn |
| Snapshot toàn bộ nội dung cho từng sinh viên | Giữ lịch sử tốt nhưng sao chép dữ liệu quá nhiều | Không chọn |
| Version mọi bảng, mọi field | Chi tiết nhưng tăng trạng thái và dependency | Không chọn |
| Course version + lesson/slide version dùng lại | Publication nhất quán, truy vết được, không sao chép file không đổi | **Chọn** |
| Event sourcing | Phải quản lý replay và projection phức tạp | Không chọn |
| Audit log cho publish/archive/restore | Nhỏ, hỗ trợ giải thích thay đổi | Chọn giới hạn |

### 2.2. Nguyên tắc vận hành

1. Mỗi khóa có tối đa một bản nháp đang chỉnh sửa và một con trỏ tới bản đã xuất bản hiện hành.
2. Course version lưu cấu trúc chương/bài. Lesson version lưu nội dung bài. Slide version lưu tham chiếu ảnh bất biến.
3. Sửa bản đã xuất bản tạo draft mới theo cơ chế copy-on-write. Nội dung không đổi được dùng lại.
4. Publish khóa học là một transaction: xác thực draft, đóng băng các version mới và chuyển con trỏ hiện hành.
5. Phiên học/lượt làm bài gắn với đúng item của course version đã chọn.
6. Xóa nội dung là gỡ membership trong draft; publish làm thay đổi có hiệu lực với lượt học mới.
7. Archive khóa học chặn lượt học mới ngay; lịch sử vẫn truy cập được theo quyền.
8. Dữ liệu thu thập gốc bất biến. Analytics và AOI mapping là kết quả có thể tính lại.
9. Các API và frontend được chuyển đồng bộ sang schema mới; không giữ adapter legacy.

Giữ FastAPI, SQLAlchemy, PostgreSQL/pgvector, Redis, Next.js và gaze service hiện có. Không bổ sung Kafka, data warehouse hoặc service riêng cho versioning.

## 3. Schema đích và danh mục cleanup

### 3.1. Người dùng và quyền

| Thành phần | Thiết kế |
|---|---|
| `users`, `auth_sessions` | Giữ chức năng đăng nhập, refresh token, khóa tài khoản; unique email không phân biệt hoa/thường |
| `user_profiles`, `student_profiles`, `teacher_profiles` | Giữ vì có dữ liệu và consumer thực tế; không gộp các vai trò thành các cột nullable trên user |
| `roles`, `user_roles` | Giữ quan hệ nhiều vai trò |
| `user_statuses`, `genders` | Bỏ lookup table cố định; dùng code với CHECK và enum tương ứng ở API |
| `course_teachers` | Giữ phân công giáo viên; owner vẫn là một FK riêng trên course |
| `enrollments` | Giữ identity đăng ký; UNIQUE course/student; lịch sử học tham chiếu enrollment |

Giữ chính sách phân quyền đang có, gom việc kiểm tra vào service chung. Mọi truy cập nội dung phải xác minh course, enrollment, version và ownership của session/attempt.

Không tạo lại `permissions`, `role_permissions`, `oauth_accounts` đã bị loại bỏ.

### 3.2. Nội dung

| Bảng | Nội dung chính và ràng buộc |
|---|---|
| `courses` | Identity, owner, `archived_at`, cấu hình tracking vận hành, `published_version_id` |
| `course_versions` | Course FK, version number, `draft/published`, generation, title/description/thumbnail asset, actor/time; tối đa một draft/course |
| `course_version_modules` | Course-version FK, `module_key` ổn định, title, position; UNIQUE vị trí và module key trong version |
| `lessons` | Identity, course FK, kind `lesson/quiz`; không giữ title/order/module mutable |
| `lesson_versions` | Lesson FK, version number, draft/published, title, actor/time |
| `course_version_items` | Course-version/module membership, lesson ID, lesson-version ID, position; một lesson xuất hiện tối đa một lần/course version |
| `slides` | Identity slide, lesson FK |
| `slide_versions` | Slide FK, revision number, image asset FK, PDF nguồn FK, source page, render metadata |
| `lesson_version_slides` | Lesson-version FK, slide-version FK, position, title, `is_key`; UNIQUE position và logical slide trong bài |

**Quyết định chuẩn hóa:**

- Không giữ bảng `modules` mutable song song với snapshot chương. `module_key` giúp đối chiếu cùng một chương giữa các course version.
- Vị trí slide và `is_key` thuộc membership của lesson version, không thuộc file hay slide identity.
- Không lưu lại title/order ở nhiều bảng như những nguồn sự thật độc lập.
- `lesson_contents` được thay bằng `slides`, `slide_versions`, `lesson_version_slides`.
- `course_statuses` được bỏ: trạng thái hiển thị suy từ archive, published pointer và draft.
- Moving lesson giữa các chương trong cùng course chỉ đổi course-version membership.
- Copy sang course khác tạo identity mới. Không hỗ trợ chuyển identity qua course trong V1.

Các membership phải cùng course và đúng lesson. Dùng composite FK cho các cặp identity/version; dùng constraint trigger cho quan hệ chéo còn lại. Không dùng `CHECK` chứa truy vấn bảng khác để giả định đã bảo đảm integrity. [PostgreSQL 16 — Constraints](https://www.postgresql.org/docs/16/ddl-constraints.html)

### 3.3. File và embedding

| Bảng | Thiết kế |
|---|---|
| `media_assets` | UUID, course FK, storage backend, object key, SHA-256, MIME, byte size, kích thước ảnh, state, created time |
| `slide_documents` | Slide-version FK, pipeline/model version, transcript, vector 1024 chiều, FTS, ingestion state/error |

Quy tắc:

- Binary ready không bị ghi đè. Dedupe theo `(course_id, sha256)`.
- Ảnh và PDF nguồn là asset riêng; nhiều slide có thể tham chiếu cùng PDF.
- Object key chứa namespace môi trường/DB instance và asset ID.
- Upload/render vào staging; chỉ gắn vào draft khi asset hoàn tất.
- Publish không đòi embedding hoàn tất, nhưng đòi file hiển thị đã ready. Chat báo phạm vi tài liệu đang xử lý khi cần.
- Embedding dựa trên nội dung bất biến; title/chương/số trang được lấy từ course-version membership khi retrieval.
- Bỏ embedding status trên slide content và bảng `lesson_content_embedding` cũ để tránh hai nguồn trạng thái.
- Không có cleanup theo “lesson cũ” hoặc “PDF version cũ”.
- GC chỉ xóa staging hoặc unpublished revision không còn tham chiếu sau 7 ngày; sau đó mới xóa asset mồ côi. Asset được published hoặc có history không bị GC.
- GC và thao tác gắn asset khóa cùng record để tránh xóa cạnh tranh.
- File lịch sử resolve chính xác qua asset ID; không fallback sang file mới nhất.
- Media endpoint kiểm tra quyền trước khi stream/cấp URL ký. Không dùng public URL làm cơ chế bảo vệ draft.

### 3.4. Quiz

| Bảng | Thiết kế |
|---|---|
| `quiz_specs` | PK/FK `lesson_version_id`; instructions, duration, due date, retry/chat policy, questions JSONB |
| `quiz_attempts` | UUID, enrollment, course-version item, lesson identity, attempt number, trạng thái, thời điểm bắt đầu/hết hạn/nộp, answers, grading result, score |

**Loại bỏ** `quiz_assignments` và `quiz_attempt_sessions` cũ.

Một quiz đã là lesson có kind `quiz`, nên không cần thêm assignment identity 1:1 chỉ để lặp course/lesson/title.

Questions giữ JSONB vì là một tài liệu đề được đọc và đóng băng nguyên khối. Không thêm bảng cho từng option khi chưa có nhu cầu ngân hàng câu hỏi độc lập. Đổi lại, API phải kiểm tra nghiêm:

- ID câu hỏi/option duy nhất trong version.
- Đáp án đúng tham chiếu option hợp lệ.
- Điểm, lựa chọn đơn/đa và cấu trúc đề hợp lệ.
- Answers lúc nộp chỉ được tham chiếu đề của attempt.

`quiz_specs` nằm riêng để role chatbot không được đọc answer key.

Ràng buộc attempts:

- UNIQUE `(enrollment_id, lesson_id, attempt_no)`.
- Partial unique: tối đa một attempt `in_progress` cho enrollment/lesson.
- `expires_at` chốt khi bắt đầu.
- Submit chỉ được chuyển một lần từ in-progress sang submitted.
- Kết quả submitted bất biến.
- Retry thêm attempt mới; không xóa/reset attempt cũ.
- GET đề không bắt đầu đồng hồ.

### 3.5. Calibration, session và gaze

| Bảng | Thiết kế |
|---|---|
| `devices` | Owner, fingerprint, con trỏ calibration hiện hành; không dùng viewport mutable làm dữ liệu lịch sử |
| `calibrations` | Device FK, model `.ubj`, model hash/version, MAE, viewport CSS, DPR, config, created time; bất biến |
| `calibration_settings` | Giữ cấu hình ngưỡng quản trị |
| `learning_sessions` | Enrollment, course-version item, optional quiz-attempt FK, calibration FK, pipeline/config, consent, start/end/expiry, trạng thái |
| `content_presentations` | Session FK, optional lesson-version-slide membership, surface, thời gian/sequence bắt đầu và kết thúc |
| `gaze_batches` | Session, presentation, optional layout snapshot, batch ID/number, sequence range, payload hash, received time, ACK counts |
| `gaze_samples` | ID, session, batch, sequence, capture monotonic time, event time UTC, viewport x/y, status, quality flags |

Cleanup:

- Gộp `calibration_sessions` và `calibration_params` thành `calibrations`.
- Bỏ `params NUMERIC[]` legacy và cơ chế ghi đè calibration.
- Bỏ cả `gaze_events` và `gaze_raw_samples` cũ; chỉ có `gaze_samples`.
- Không lặp viewport, DPR, calibration dimensions, layout key, surface và metadata JSON trên mọi sample.
- Không lưu slide coordinates như một nguồn tọa độ thứ hai; tính từ raw và transform snapshot.
- Session ID trong sample là denormalization có chủ đích để index/query theo session; composite FK buộc nó khớp batch.

Session có tracking phải pin calibration phù hợp owner/device/viewport. Thay viewport/calibration tạo session mới. Session đã đóng không được mở lại.

Một presentation đại diện một lần xem slide; quay lại slide đó tạo presentation mới. Quiz dùng presentation không có slide membership, nhưng vẫn gắn với đúng attempt/version.

### 3.6. AOI, analytics và chat

| Bảng/nhóm | Thiết kế |
|---|---|
| `aoi_sets` | Scope slide/viewport, slide-version FK hoặc UI-schema version, revision, draft/published |
| `aoi_definitions` | Set FK, code, name, parent, hình học rect cho slide hoặc semantic selector cho UI |
| `aoi_layout_snapshots` | Presentation, UI AOI set, capture time/sequence, layout generation, image transform |
| `aoi_layout_rects` | Snapshot, semantic code, element key, rect viewport |
| `analysis_runs` | Session, AOI set, time range, batch watermark, algorithm/config, trạng thái |
| `aoi_hits` | Run, sample ID + event time, definition; composite unique, không cần surrogate ID |
| `presentation_metrics` | Presentation + algorithm version, watermark, counts/durations, heatmap grid |
| `chat_sessions`, `chat_messages` | Giữ; thêm course-version/attempt context rõ ràng |
| `content_audit_events` | Chỉ ghi publish/archive/restore: actor, course, version, action, timestamp, request ID |
| `app_metadata`, `schema_migrations` | DB instance/environment/schema generation và migration checksum |

Loại bỏ:

- `aoi_regions`, `aoi_dwell_stats` cũ.
- `gaze_slide_stats`, `gaze_session_stats`.
- `heatmap_aggregates`, `engagement_scores`, `slide_coverage_stats`, `lesson_mastery_scores`.

Các metric vẫn cần được phục vụ, nhưng tính từ `presentation_metrics` qua SQL views/service:

- Tổng hợp theo session/student/lesson version.
- Class heatmap cộng grid cùng version.
- Attention/coverage và điểm trọng tâm tính theo định nghĩa đã version hóa.
- Không giữ nhiều bảng cùng lưu lại một tỷ lệ dưới những tên khác nhau.

`analysis_runs` phục vụ phân tích có thể tái lập; dashboard projection phục vụ hiển thị nhanh. Hai loại có mục đích riêng.

Một analysis run xử lý **một session, một AOI set, một khoảng thời gian**. Rebuild cấp course mở rộng thành nhiều run; không cần hệ thống job tổng quát mới.

## 4. Luồng nghiệp vụ, API và thu thập dữ liệu

### 4.1. Draft/publish/delete

- Editor lấy hoặc tạo draft course version từ bản published.
- Clone cấu trúc chương/item; reuse lesson/slide versions chưa đổi.
- Chỉnh sửa bài tạo draft lesson version khi cần.
- Publish kiểm tra toàn bộ working tree: file ready, đề hợp lệ, thứ tự và quyền hợp lệ.
- Lesson trống/quiz chưa hợp lệ chặn publish; UI chỉ rõ item cần hoàn thiện hoặc gỡ.
- Lưu draft không làm ẩn hoặc sửa bản published hiện hành.
- Mọi thay đổi draft có `expectedGeneration`; mutation và publish khóa course để chống lost update.
- Batch remove/reorder là một transaction, không áp dụng một phần.

**Ví dụ:**

| Tình huống | Xử lý |
|---|---|
| Xóa slide S3 đã có gaze | V1 giữ membership/asset của S3; V2 bỏ S3. Gaze V1 vẫn đối chiếu được |
| Đưa slide 3 lên đầu | Chỉ đổi membership position trong V2; không copy file, không đổi thứ tự lịch sử V1 |
| Thay ảnh S3 | Tạo slide revision mới; giữ revision cũ và AOI cũ |
| Thay toàn PDF | Tạo các slide mới trong draft. Không tự ghép lineage bằng số trang; chỉ dedupe binary theo hash |
| Xóa chương | Bỏ chương và các item khỏi draft; version đã xuất bản vẫn giữ |
| Sửa đáp án khi đang làm | Attempt cũ dùng đề/đáp án/deadline cũ; attempt mới dùng version mới |
| Retry | Tạo attempt kế tiếp; giữ điểm, chat và gaze của lần trước |
| Archive khóa học | Chặn lượt mới; session/attempt đang chạy được hoàn tất theo thời hạn đã chốt |

Mặc định session lesson hết hạn sau 12 giờ; quiz theo deadline. Cho gửi nốt batch capture trước lúc đóng trong 2 phút.

Nếu version đổi giữa GET outline và POST start, trả `409 content_changed`. Resume attempt đã tồn tại dùng context của attempt đó, không bị buộc sang đề mới.

### 4.2. Hợp đồng API

Giữ prefix `/teacher` và `/api` đang dùng; thay body/response đồng bộ với frontend.

| API | Hành vi |
|---|---|
| `GET /teacher/courses/{id}/draft` | Working tree và generation |
| CRUD nội dung trong draft | Nhận `expectedGeneration`, trả generation mới và identity/version IDs |
| `POST /teacher/courses/{id}/publish` | Publish toàn khóa, trả courseVersionId |
| `GET /teacher/courses/{id}/versions` | Danh sách và xem lịch sử |
| `POST /teacher/courses/{id}/restore` | Tạo draft từ version được chọn |
| `GET /api/courses/{id}` | Outline bản published hiện hành |
| `POST /api/learning-sessions` | Xác thực enrollment và version; cấp context cố định |
| `GET /api/learning-sessions/{id}/contents` | Nội dung đúng phiên đã cấp |
| `POST /api/lessons/{id}/attempts` | Bắt đầu lượt làm, hỗ trợ idempotency |
| `POST /api/attempts/{id}/submit` | Chấm theo version của attempt |
| `GET /api/lessons/{id}/attempts` | Lịch sử các lượt của người dùng được phép |
| `POST /api/learning-sessions/{id}/presentations` | Mở lần hiển thị slide/quiz |
| `POST /api/presentations/{id}/layouts` | Lưu hình học bất biến |
| `POST /api/learning-sessions/{id}/gaze-batches` | Ingest có ACK/idempotency |
| API AOI/analysis | Tạo/publish set, tạo run, đọc status/result/export |

Không duy trì endpoint assignment legacy hoặc auto-create learning session khi batch thiếu context.

### 4.3. Gaze và tọa độ

1. Khi capture frame, frontend chốt `frameId`, sequence, monotonic timestamp, presentation và layout generation.
2. Metadata và JPEG được truyền nguyên tử trong protocol có version; gaze service echo frame ID.
3. Khi inference trả về, dùng context lúc capture, kể cả người dùng đã chuyển slide.
4. Batch chỉ chứa một presentation/layout context.
5. Backend ghi receipt và samples trong cùng transaction, sau đó mới ACK.

Tọa độ chuẩn:

- Viewport CSS, gốc trên-trái; x/y có thể ngoài `[0,1]`.
- No-face/error lưu tọa độ NULL.
- Snapshot lưu vùng ảnh được vẽ thật sau `object-fit: contain`, không chỉ container.
- Mapping slide:
  `slideX = (viewportX × viewportWidth − imageLeft) / imageWidth`; tương tự Y.
- Frontend thống nhất helper AOI và slide về cùng hệ viewport.
- Thay zoom/DPR/viewport cần dừng tracking và hiệu chỉnh lại.
- Layout chưa xác định vẫn được lưu raw với quality phù hợp; không gắn snapshot tương lai để “sửa” lịch sử.

Timestamp UTC được suy từ mốc server/client lúc mở phiên và delta monotonic; lưu clock uncertainty ở session. Không thay timestamp bất thường bằng `now()` một cách âm thầm.

“Raw” ở đây là output của pipeline inference/calibration/smoothing, không phải video camera nguyên gốc. Session phải lưu phiên bản pipeline và cấu hình smoothing.

### 4.4. Queue và integrity

- Client giữ batch trong IndexedDB tới khi nhận ACK.
- Một request đang gửi/session; retry giữ nguyên batch ID và payload.
- UNIQUE `(session_id, batch_id)` và `(session_id, batch_no)`.
- Server khóa session ngắn, yêu cầu batch number đúng thứ tự và sample sequence tăng.
- Retry sau commit nhưng mất response trả ACK cũ, không cộng lại counts.
- Cùng batch ID nhưng khác payload trả 409.
- ACK trả số received/stored/duplicate/rejected.
- Rate limit theo user/session, hỗ trợ `Retry-After`; kiểm thử nhiều sinh viên chung NAT.
- Queue tối đa 10 phút hoặc 10 MB/session. Khi vượt giới hạn, báo lỗi và gap; không giả định dữ liệu đã được lưu.
- Theo dõi dropped frames/gaps; việc giữ mọi output không có nghĩa camera hoặc inference không bỏ frame.

### 4.5. AOI và phân tích

- AOI slide: rectangle chuẩn hóa theo đúng slide revision.
- AOI UI: geometry từ snapshot; semantic code thuộc UI schema đã version hóa.
- Bộ AOI published bất biến. Sửa tạo set revision mới.
- Cho phép AOI chồng lấn; ghi các hits tương ứng, không cộng tổng dwell chồng lấn thành thời lượng phiên.
- AOI slide mới chỉ áp vào raw có đúng stimulus/transform.
- AOI DOM bổ sung sau này chỉ map được nếu snapshot đã ghi geometry/element tương ứng.
- Analysis run chốt batch watermark và khoảng `[from,to)`.
- Run mới không xóa kết quả run cũ. Retry cùng run chỉ sửa kết quả chưa hoàn tất thuộc chính run đó.
- Hit liên kết raw qua `(sample_id, event_time)` và kiểm tra definition thuộc AOI set của run.
- Dwell tính từ monotonic delta, tách theo presentation và ngắt tại no-face/gap trên 250 ms. Đây là cấu hình thuật toán cần kiểm định, không phải khẳng định khoa học.
- Export gồm raw, context phiên/presentation, calibration metadata, layout, content/asset manifest, AOI và algorithm version.

### 4.6. Chat/RAG

- Cả vector search và keyword search lọc course-version membership **trước LIMIT**.
- Không đưa title/chương/order mutable vào embedding text.
- Citation chứa courseVersionId, lessonVersionId, slideVersionId, membership và asset ID.
- Chat quiz lấy attempt cụ thể; lượt đã nộp cũ không được mở quyền xem đáp án của lượt mới.
- Thay toàn bộ query `scalar_one_or_none()` hoặc join đang giả định một attempt/student.
- Role chatbot chỉ được đọc nội dung công khai phục vụ retrieval và ghi `slide_documents`; không đọc `quiz_specs`, attempts hoặc users.
- Backend tiếp tục làm nguồn kiểm tra quyền và cung cấp ngữ cảnh quiz đã lọc.

## 5. Baseline, reset, triển khai và nghiệm thu

### 5.1. Baseline migration sạch

Thay thư mục migrations hiện tại bằng:

- `001_baseline.sql`: toàn bộ schema, constraints, indexes, triggers, views và partition helpers.
- `002_reference_seed.sql`: roles và cấu hình hệ thống mặc định; không chứa tài khoản mẫu.
- Seed development là thao tác riêng, chỉ chạy trong môi trường development/test.

Các migration cũ được xóa khỏi cây chạy; lịch sử vẫn có trong Git. Không tạo chuỗi migration “drop legacy rồi dựng lại”, không giả lập đã áp baseline bằng checksum cũ.

Baseline gồm:

- `vector`, `unaccent`; không cài `pg_trgm` vì hiện không tìm thấy query/index sử dụng.
- FK/index được đặt tên nhất quán với ORM.
- Trigger bảo vệ published version, immutable assets/calibrations và submitted attempts.
- CHECK enum/status, số thứ tự, duration, score, coordinates hữu hạn.
- Views analytics và view nội dung dành cho chatbot.
- `app_metadata` có schema generation và DB instance ID.

Runner migration:

- Một kết nối giữ advisory lock trong suốt lượt chạy.
- Schema changes và checksum record commit atomically cho từng migration.
- Mất lock hoặc checksum mismatch phải fail.
- Database có lịch sử migration cũ phải báo cần reset có chủ đích.
- Bỏ cơ chế tự baseline/replay để “đoán” schema hiện tại.
- Dev/test/CI dùng cùng runner; bỏ parser SQL tự viết trong pytest fixture.

### 5.2. Reset development có kiểm tra đích

Viết lại [scripts/reset_db.sh](</home/hieu/Documents/NCKH Eyetracking/EyeLearning/scripts/reset_db.sh>) với hai chế độ: preview mặc định và apply tường minh.

Trước apply phải kiểm tra lại:

1. Docker endpoint là local socket.
2. Container PostgreSQL có Compose project, service, config path và working directory đúng repo.
3. Database đích khớp `eyetracking`, không phải database hệ thống.
4. Backend DSN khớp database và PostgreSQL đã xác minh.
5. Tham số `--database` và `--confirm-reset` trùng khớp.
6. Tên database được quote bằng cơ chế identifier của PostgreSQL, không nối chuỗi SQL tùy ý.

Trình tự:

1. Dừng backend/chatbot/worker thuộc project này để nhả kết nối.
2. Kiểm tra các kết nối còn lại tới đúng database; gặp client không xác định thì dừng và báo.
3. Drop/recreate riêng `eyetracking`, kết nối qua database quản trị. `DROP DATABASE` chạy ngoài transaction. [PostgreSQL 16 — DROP DATABASE](https://www.postgresql.org/docs/16/sql-dropdatabase.html)
4. Chạy baseline, reference seed, grants dành riêng cho app.
5. Tạo DB instance ID mới và seed development nếu được chọn.
6. Chạy schema/API smoke tests.
7. Chỉ khởi động runtime khi các gate thành công; lỗi migration không được bỏ qua bằng `|| true`.

Không sử dụng `docker compose down -v`, xóa PostgreSQL volume hoặc reset các database khác.

R2/local media cũ được giữ nguyên. Dữ liệu mới dùng namespace chứa DB instance ID. Redis cũng dùng namespace mới; không `FLUSHALL`.

Roles runtime dùng tên riêng cho project, không cấp quyền superuser. Script không sửa role có sẵn ngoài phạm vi đã xác minh. Đây là thay đổi provisioning riêng, không lẫn vào reset dữ liệu.

### 5.3. Index và dung lượng

- Partition `gaze_samples` theo tháng của `event_time`.
- PK `(id,event_time)`; index `(session_id,event_time)` và `(batch_id,event_time)`.
- Không tạo index lặp lại prefix đã có trong UNIQUE.
- Không tạo GIN cho metadata/answers nếu chưa có query cần dùng.
- `gaze_batches` không partition để giữ uniqueness batch/session.
- Constraint UNIQUE trên bảng partition phải chứa partition key; không tạo UNIQUE chỉ `(session,sequence)` rồi giả định được bảo đảm toàn cục. [PostgreSQL 16 — Partitioning](https://www.postgresql.org/docs/16/ddl-partitioning.html)
- Baseline tạo partition tháng trước, hiện tại và ba tháng tới; job duy trì hàng ngày, có default partition dự phòng và cảnh báo.
- Query analytics/export luôn có time range; export dùng cursor/stream.
- `slide_documents`: GIN FTS và HNSW cosine cho vector 1024 chiều.
- Metrics worker dùng watermark bền trong PostgreSQL; Redis chỉ là cache/throttle.
- Cache key chứa version/algorithm/watermark; không ghi kết quả cũ vào cache generation mới.
- Không tự purge raw hay published history trong V1.

Dự toán: 20 output/s tương ứng 72.000 samples/giờ/sinh viên; 100 sinh viên tương ứng 7,2 triệu samples/giờ. Đo row/index size thực tế trước khi dự toán dung lượng. Load test ingestion không chứng minh GPU đủ chạy inference cho cùng số người.

### 5.4. Các phase theo dependency

#### Quy tắc triển khai và giới hạn breaking changes

- Thứ tự bắt buộc: **Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6**. Công việc tài liệu/UI có thể chuẩn bị sớm, nhưng không đóng phase trước khi dependency đạt gate.
- Làm trên nhánh tái cấu trúc; mỗi phase là một nhóm commit review được. Không reset development để bắt đầu thử một phase.
- Phase 1–5 dùng PostgreSQL và media test riêng; chưa trỏ backend/frontend/chatbot đang dùng sang schema mới. Mặc định tạo database `eyelearning_refactor_test` trong PostgreSQL local đã xác minh; nếu tên đã tồn tại mà chưa xác nhận ownership thì dừng, không tự drop.
- “Kiểm thử độc lập” nghĩa là module/service/route của phase có fixture và test app tối thiểu riêng. Không yêu cầu toàn bộ ứng dụng cũ chạy với ORM mới ở mọi commit trung gian; full-stack mới là gate bắt buộc trước Phase 6.
- Không tạo lớp tương thích dữ liệu hoặc API legacy lâu dài. Hạn chế breaking changes bằng contract-first, khoanh vùng thay đổi, giữ UI chức năng hiện có và cutover đồng bộ một lần sau khi toàn stack mới được kiểm thử.
- Không dùng `Base.metadata.create_all()` thay baseline trong test; SQL baseline là schema chuẩn, ORM được kiểm tra đối chiếu catalog.
- Baseline có thể được hoàn thiện trong nhánh chưa phát hành và DB test có thể rebuild theo guard. Sau lần nghiệm thu ở Phase 6, khóa checksum baseline; mọi thay đổi sau đó dùng migration mới.
- Mỗi phase phải cập nhật bằng chứng kiểm thử và phần trạng thái bên dưới. Không đánh dấu hoàn tất khi test bị skip do thiếu PostgreSQL hoặc consumer bắt buộc chưa được kiểm tra.

| Phase | Dependency | Schema/migration | Gate độc lập |
|---|---|---|---|
| 0 | Không | Chỉ đặc tả và reset preview; không áp migration | Guard tests, contract fixtures |
| 1 | 0 | Baseline mới và reference seed, chỉ trên DB test riêng | Catalog/ORM/constraint/privilege tests |
| 2 | 1 | Dùng các bảng content/media/audit của baseline | Content service/route/UI tests |
| 3 | 2 | Dùng quiz/calibration/session của baseline | Attempt/session/calibration tests |
| 4 | 3 | Dùng presentation/layout/batch/sample của baseline | Protocol/queue/ingestion tests |
| 5 | 4 | Dùng AOI/analysis/metrics/chat/document của baseline | Analytics/RAG/export và full-stack tests |
| 6 | 0–5 đạt gate | Rebuild đúng development DB bằng baseline đã nghiệm thu | Rebuild hai lần trên test, smoke/E2E/load gates |

#### Phase 0 — Contract, test isolation và reset guard

**Mục tiêu và phạm vi:** Chốt tên/quan hệ schema, DTO và ranh giới reset trước khi thay consumer. Xây công cụ xác minh đích, chưa thực hiện reset development.

**File/module cần sửa:**

- `scripts/reset_db.sh`, `scripts/test_backend.sh`, `scripts/seed_dev.sh`, `scripts/create_partitions.sh`.
- `db/migrate.sh`, `Dockerfile.migrations`, cấu hình compose/test; đặc tả API/schema trong `docs/` và `PLAN.md`.
- Test infrastructure trong `backend/tests/conftest.py`, `services/chatbot/tests/`, `frontend/e2e/fixtures.ts` và cấu hình Playwright.

**Công việc cụ thể:**

1. Chốt DTO identity/version/membership/attempt, mã lỗi 409 và contract generation/idempotency ở mục 4; lập bảng route cũ → route mới và consumer tương ứng.
2. Định nghĩa danh mục bảng/cột/FK/index/view đích theo mục 3; xác định cột immutable và transition được phép của từng trạng thái.
3. Viết reset preview/guard: kiểm tra Docker socket/project/path/container/DSN/database; tham số apply và confirm tường minh; quote identifier an toàn.
4. Tạo test guard bằng process adapter giả lập, bảo đảm dry-run không gọi stop/drop/seed. Không test guard bằng cách thử drop database thật.
5. Tách configuration cho DB test riêng, media root tạm và R2 mock. Playwright không được mặc định gọi backend development đang dùng.
6. Quy định DB instance namespace cho Redis/media; xác định tên roles riêng và phạm vi grants. Không log secret trong preview/evidence.

**Dependencies và migration:** Không có dependency trước. Chỉ chuẩn bị runner/provisioning; chưa áp baseline mới và chưa sửa dữ liệu hiện tại.

**Test cases:** Đích đúng; remote Docker; project/path khác; database hệ thống; DSN không khớp; tên có ký tự đặc biệt; thiếu confirm; DB test đã tồn tại không rõ ownership; lỗi kiểm tra kết nối; dry-run không có side effect.

**Tiêu chí nghiệm thu:** Contract và danh mục consumer không còn quyết định kiến trúc mở; guard từ chối mọi đích ngoài phạm vi; unit tests chạy không cần chạm dữ liệu đang dùng; có cấu hình test isolation rõ ràng.

#### Phase 1 — Baseline sạch, ORM và integrity

**Mục tiêu và phạm vi:** Dựng schema đích thống nhất từ database rỗng; loại bỏ phụ thuộc migrations lịch sử và kiểm chứng integrity tại DB.

**File/module cần sửa:**

- Thay nội dung `db/migrations/` bằng `001_baseline.sql`, `002_reference_seed.sql`; sửa `db/migrate.sh`, `db/seed_dev_users.sql`, `db/README.md`.
- Toàn bộ `backend/app/models/`, model registration và `backend/app/db/`; bổ sung model cho assets/documents và các bảng mới.
- Provisioning grants trong `ops/create_chatbot_role.sh`; fixture/schema tests trong `backend/tests/` và chatbot database tests.

**Công việc cụ thể:**

1. Tạo bảng theo dependency: identity/auth → assets → course/lesson/slide versions và membership → quiz/calibration/session → presentation/layout/gaze → AOI/analysis/metrics/chat/audit. Thêm FK tạo vòng tham chiếu sau khi cả hai bảng tồn tại.
2. Tạo extensions, constraints, immutable triggers, views, index và partition helpers đã chọn; trigger kiểm tra cùng course/session/version ngoài phạm vi FK cục bộ.
3. Đồng bộ ORM: bỏ model/cột legacy, bỏ `delete-orphan` và cascade có thể xóa history; giữ tên constraint nhất quán với SQL.
4. Runner giữ lock và ghi checksum nguyên tử; baseline từ chối schema cũ thay vì tự đánh dấu đã áp. Bỏ parser/replay migration riêng của pytest.
5. Reference seed chỉ chứa roles/config hệ thống. Dev seed tạo đủ profile/role nhưng không tự đổi mật khẩu tài khoản đã tồn tại.
6. Provision runtime role riêng, kiểm tra role đã tồn tại trước khi thay quyền; chatbot chỉ có quyền trên view công khai và documents. Không sửa các cluster roles không thuộc project.
7. Áp baseline vào DB test được Phase 0 xác minh. Chưa chạy bất kỳ consumer cũ nào trên DB này.

**Dependencies và migration:** Sau Phase 0. Toàn bộ schema mới nằm trong baseline; không viết migration nâng cấp 28-file history và không backfill dữ liệu.

**Test cases:** Bootstrap rỗng; rerun runner; checksum mismatch; lock contention; transaction lỗi không ghi migration thành công; catalog khớp ORM; illegal FK/context; immutable update/delete; enum/score/coordinate constraints; grants chatbot; month boundary/default partition.

**Tiêu chí nghiệm thu:** Baseline dựng được trên DB test từ đầu; rerun không nhân bản schema/seed; các bảng/cột legacy không tồn tại; DB từ chối sửa/xóa history trái quy tắc; ORM import/mapping và schema tests đạt.

#### Phase 2 — Content, media, draft/publish và reader

**Mục tiêu và phạm vi:** Hoàn thiện vòng quản lý nội dung từ draft đến published/history, gồm CRUD mọi cấp và quản lý asset bất biến.

**File/module cần sửa:**

- Backend routes `courses.py`, `modules.py`, `module_items.py`, `lessons.py`, `media.py`, `enrollments.py`, `admin.py`; `api/access.py`, `api/deps.py`, course schemas.
- Services content version/publish mới, `media_storage.py`, `course_stats.py`; script media migration cũ được loại khỏi đường vận hành mới.
- Frontend `components/teacher/content-editor/`, course workspace/settings/list, student outline/reader; `lib/api/teacher.ts`, `lib/api/student.ts`, `lib/types/domain.ts`, hooks/query keys.

**Công việc cụ thể:**

1. Implement working draft, clone-on-write, generation guard, CRUD/batch remove/reorder và publish nguyên tử; không dùng status PATCH cũ để giả lập publication.
2. Chuyển module/lesson/slide title/order/key flags sang đúng version/membership; loại mọi truy vấn lấy tất cả slide revisions theo lesson ID rồi coi là hiện hành.
3. Upload/render staging và asset registry; publish chỉ nhận file ready. Tách lỗi upload khỏi draft đang dùng và version published.
4. Xây outline theo course version; history/media resolve đúng asset và quyền, không fallback latest. Chuẩn bị reader nhận version/membership IDs cho Phase 3–4.
5. UI hiển thị published vs draft, preview publish, lỗi item không hợp lệ, batch actions và archive/restore. Nút lưu nháp không rút nội dung đang published.
6. Bỏ prefix cleanup khi thay PDF/delete. GC chỉ xóa staging/unpublished orphan sau reference check và grace period; dùng R2 mock cho mọi test cleanup.

**Dependencies và migration:** Sau Phase 1. Dùng content/media tables của baseline; consumer tests chạy trên DB test. Chưa cutover development hoặc chạy GC trên R2 thực.

**Test cases:** CRUD từng cấp; nhiều slide atomic; reorder không nhân bản asset; thay PDF; concurrent publish/edit/upload; invalid quiz/content chặn publish; archive/restore; upload lỗi giữa render/commit; GC cạnh tranh attach; lịch sử đọc đúng file; quyền cross-course và draft leakage.

**Tiêu chí nghiệm thu:** Sinh viên xem published tree đúng trong khi giáo viên tiếp tục sửa draft; version cũ và checksum file không đổi; generation conflict trả 409; content service/route và UI tests đạt. Session pinning hoàn chỉnh được kiểm tra ở Phase 3.

#### Phase 3 — Quiz attempts, calibration và learning sessions

**Mục tiêu và phạm vi:** Giữ nguyên đề, deadline và calibration của dữ liệu học phát sinh mới; loại retry xóa lịch sử và reopen session cũ.

**File/module cần sửa:**

- Backend `api/routes/assignments.py`, `gaze.py` phần session, `calibration.py`; schemas quiz/calibration/gaze; các services session/attempt dùng chung.
- Frontend `hooks/use-quiz.ts`, `lib/quiz-store.ts`, `lib/api/quiz.ts`, quiz components, calibration flow/API và reader lifecycle.
- Các caller đang dùng assignment ID hoặc giả định một attempt: chuẩn bị contract cho chat/chat access/internal queries sẽ tích hợp ở Phase 5.

**Công việc cụ thể:**

1. Thay assignment identity bằng lesson quiz/version và `quiz_specs`; validate toàn bộ question/option IDs và grading input.
2. Implement POST start idempotent, GET read-only, submit một lần và retry tạo attempt mới; lưu deadline và grading result theo version đã pin.
3. Implement session start/resume/close/expiry, kiểm tra enrollment/course-version item. Chỉ resume session còn mở của cùng client/context; không đổi thông số session lịch sử.
4. Lưu calibration mới mỗi lần, cập nhật device pointer; session tham chiếu model/hash/viewport/pipeline đã xác minh. Bỏ fallback model legacy và overwrite cũ.
5. Tách course tracking setting khỏi student consent. Cập nhật frontend cache/local-store keys theo attempt/session/version; lịch sử bài làm chọn attempt cụ thể.
6. Chuẩn bị API context dùng chung cho capture, grading và chat; chấm/hiển thị đáp án không được lấy từ latest quiz version.

**Dependencies và migration:** Sau Phase 2. Dùng quiz/calibration/session schema baseline. Không chuyển các query chat cũ sang DB mới trước khi Phase 5 đạt gate.

**Test cases:** Publish/sửa đề khi đang làm; deadline bị đổi ở bản mới; double start/submit; retry concurrent; latest-score/history; calibration mới không đổi session cũ; sai device/course/enrollment; consent false; closed session không reopen; reconnect attempt cũ sau publication mới.

**Tiêu chí nghiệm thu:** Mỗi attempt/session truy ra đúng version/calibration; retry giữ đủ lượt cũ; submitted results bất biến; frontend quiz/session tests đạt. Không còn runtime fallback tự suy context từ latest content.

#### Phase 4 — Capture context, layout và gaze ingestion

**Mục tiêu và phạm vi:** Lưu mọi output inference đúng context capture, nhận batch idempotent và không mất buffer trước ACK.

**File/module cần sửa:**

- `services/gaze/app/api/session.py`, schemas và inference protocol; tests gaze service.
- Backend gaze/presentation/layout routes và schemas, batch-ingestion service, rate-limit dependency và configuration.
- Frontend `use-gaze-tracker.ts`, `use-aoi-snapshot.ts`, `learning-reader.tsx`, `calibration-geometry.ts`, `lib/aoi/measure.ts`, API client và module queue IndexedDB mới.

**Công việc cụ thể:**

1. Version protocol frame metadata+JPEG, echo frame ID/capture time; chốt presentation/layout generation tại capture và bảo toàn qua inference/reconnect.
2. Tạo/đóng presentation khi đổi slide/quiz context. Thống nhất viewport coordinate contract; snapshot chứa painted image rect và geometry cần thiết.
3. Layout invalidation ngay khi đổi; state/dedupe theo session/presentation/generation; ignore gaze overlay, tránh debounce starvation và loại response cũ. Snapshot lỗi được retry, raw ghi quality unknown.
4. Implement queue bền với batch ID/number, ACK, backoff/Retry-After, giới hạn queue và gap telemetry. Batch không trộn presentation/layout; đổi context phải tách buffer.
5. Ingest transaction ghi receipt+samples, khóa session ngắn để kiểm thứ tự; duplicate trả ACK cũ, sai payload trả 409. Lưu mọi output, không ghi `gaze_events` song song hoặc downsample trước storage.
6. Rate limit theo user/session, quota IP riêng; áp consent và close grace. Metadata calibration/viewport/pipeline lấy từ context bất biến, không lặp tùy tiện từng sample.

**Dependencies và migration:** Sau Phase 3. Dùng presentation/layout/batch/sample baseline; AOI analysis chưa bắt buộc để nghiệm thu ingestion. Không đổi protocol riêng một đầu trên stack đang dùng.

**Test cases:** Inference trễ qua navigation; snapshot cũ; session mới cùng layout; observer có gaze-dot liên tục; letterboxing/scroll/zoom; no-face/error/offscreen; mất ACK sau commit; batch retry/sai thứ tự/payload; queue storage lỗi; nhiều tab/chung NAT; expired session/grace; consent bị thu hồi.

**Tiêu chí nghiệm thu:** Batch đã ACK không mất/trùng; raw gắn đúng stimulus hoặc có quality unknown rõ ràng; counters không tăng lặp; tất cả output nhận được có stored/rejected/gap accounting; protocol/backend/frontend queue tests đạt.

#### Phase 5 — AOI, metrics, export và Chat/RAG

**Mục tiêu và phạm vi:** Phân tích tái lập từ gaze gốc, phục vụ dashboard và trợ lý học tập theo đúng phiên bản nội dung/lượt làm.

**File/module cần sửa:**

- Backend AOI/analytics routes/services/schemas, `mastery.py`, `course_stats.py`, student/teacher metrics consumers; worker và export module mới.
- Backend `chat.py`, `chat_internal.py`, `chat_access.py`, `study_chat.py`, `embedding.py`.
- Chatbot `services/ingest.py`, `workflow/retrieval.py`, `workflow/lms.py`, citations, context schemas và database grants.
- Frontend AOI editor/preview, heatmap, students tab, chat hooks/components và history navigation.

**Công việc cụ thể:**

1. Implement AOI sets draft/published và rect definitions cho slide/UI; scope/parent/cross-course validation; published set không bị sửa trực tiếp.
2. Implement analysis runs một session/set/time range, chốt batch watermark; run-scoped hits và retry không tác động run khác. Rebuild course mở rộng thành nhiều run có quyền rõ ràng.
3. Worker tính presentation metrics/heatmap grid từ raw theo watermark; SQL views/services phục vụ metrics hiện có. Bỏ các consumer bảng aggregates legacy; định nghĩa algorithm/version cho duration/coverage/mastery.
4. Export streaming gồm raw và manifest nối đủ nội dung/calibration/layout/AOI; không đọc cả course vào RAM. Cache key và invalidation không cho kết quả stale ghi vào generation mới.
5. Ingest transcript/vector theo nội dung bất biến; retrieval lọc version trước LIMIT; citation resolve membership/asset lịch sử.
6. Thay mọi single-attempt query và context key cũ; chatbot restriction/reveal theo attempt cụ thể. Kiểm tra DB role không đọc quiz specs/users/attempts; hint/review do backend cung cấp theo quyền.
7. Hoàn thiện full-stack mới với baseline, reference/dev seed và fixtures; bỏ route/import/frontend branch legacy đã hết consumer.

**Dependencies và migration:** Sau Phase 4. Dùng AOI/analysis/metrics/chat/documents baseline và views; có thể hoàn thiện baseline trên DB test trước nghiệm thu cuối. Chưa reset development.

**Test cases:** AOI chồng lấn/parent; annotation mới trên dữ liệu cũ có/không đủ geometry; run time range và watermark; retry worker; stable results; version-separated metrics; export round-trip; retrieval loại draft; reorder không re-embed; citation cũ; attempt cũ không mở quyền attempt mới; Redis lỗi; cache invalidation race.

**Tiêu chí nghiệm thu:** Full-stack E2E trên DB test mới đạt; raw và submitted attempts không bị phân tích sửa; metrics/export/RAG đều dùng version đúng; không còn consumer runtime đọc schema legacy; quyền chatbot được kiểm chứng bằng connection role thực.

#### Phase 6 — Rebuild development, load test và bàn giao

**Mục tiêu và phạm vi:** Áp bộ thay đổi đã kiểm thử vào riêng development DB đã xác minh, khởi động toàn stack mới và ghi bằng chứng vận hành.

**File/module cần sửa:**

- `docker-compose.yml`, `Dockerfile.migrations`, `.env.example`/tài liệu cấu hình, `scripts/reset_db.sh`, scripts seed/test/partition.
- `ops/maintain_partitions.sql`, provisioning grants và worker configuration; `README.md`, `backend/README.md`, `db/README.md`, tài liệu services/frontend liên quan.
- Load/smoke/E2E tests và evidence trong `docs/test-evidence/`; cập nhật trạng thái `PLAN.md`.

**Công việc cụ thể:**

1. Chạy lại bootstrap/reset hai lần trên DB test thuộc project, so schema/reference seed và xác nhận các DB khác không đổi. Hoàn tất toàn bộ test matrix mục 5.5.
2. Build tất cả images từ cùng revision; kiểm tra schema generation lúc startup, từ chối backend/worker cũ với DB mới. Chốt baseline checksum sau nghiệm thu.
3. Reverify development target ngay trước apply; chỉ khi các gate trước đạt mới chạy guarded reset `eyetracking`. Không xóa volume, R2 bucket hoặc các database khác.
4. Áp baseline, seed và grants; chuyển runtime DSN/namespace mới đồng bộ. Chỉ start backend/chatbot/worker khi migration và schema smoke tests đạt.
5. Chạy smoke lifecycle, E2E có học/sửa/xóa/retry/gaze/AOI/history; kiểm tra health và logs. Queue/browser state cũ được invalidate theo schema/DB-instance generation, không đẩy batch cũ vào database mới.
6. Đo synthetic ingestion 2.000 samples/s trong 30 phút và backlog/ACK/DB size; benchmark inference GPU riêng. Xác minh default partition, worker recovery, export memory và Redis fallback.
7. Ghi kết quả, schema generation, test configuration và phạm vi reset; ghi nhận hạn chế chưa đạt thay vì đánh dấu hoàn tất.

**Dependencies và migration:** Phase 0–5 đạt gate. Đây là phase duy nhất được reset database development đang dùng; áp baseline sạch, không chạy migrations cũ.

**Test cases:** Các gate mục 5.5–5.6; reset target mismatch ngay trước apply; migration fail thì runtime không start; stale client/version; service restart; worker crash; shared NAT; missing storage object; full data collection và historical reads sau publish/archive.

**Tiêu chí nghiệm thu:** Toàn stack mới chạy với schema sạch, không thiếu FK/runtime dependency; E2E và load report có kết quả thực; dữ liệu đã ACK đối chiếu được; không ảnh hưởng tài nguyên ngoài phạm vi. Sau phase này không rollback sang code cascade cũ trên dữ liệu mới; nếu cần rollback, dùng phiên bản hiểu schema mới hoặc tạm read-only. Vì development có thể reset, muốn reset thêm vẫn phải qua guard và không được coi dữ liệu nghiên cứu tương lai là disposable.

#### Theo dõi trạng thái

| Phase | Trạng thái | Bằng chứng cần bổ sung khi triển khai |
|---|---|---|
| 0 | Hoàn tất | `docs/refactor/contracts.md`, `docs/refactor/schema-catalog.md`, `docs/refactor/test-isolation.md`; `backend/tests/test_reset_guard.py` (13 passed); reset preview chạy trên Docker local |
| 1 | Hoàn tất | `db/migrations/001_baseline.sql`, `002_reference_seed.sql`; `db/migrate.sh`; `backend/tests/test_schema.py` (12 passed); `scripts/test_migrations.sh` (7 passed); `scripts/test_db.sh`; grants `chatbot_reader` đã kiểm chứng |
| 2 | Hoàn tất (content/media/reader) | `backend/app/services/content.py`; routes `courses/modules/module_items/lessons/media/enrollments/quiz_specs`; `backend/tests/test_content_phase2.py` (2 passed); frontend typecheck + 52 unit tests + 62 E2E passed. Quiz attempts/gaze/analytics thuộc Phase 3–5. |
| 3 | Hoàn tất (quiz/session/calibration) | `quiz_attempts.py`, `learning_sessions.py`, `calibration.py`; `backend/tests/test_quiz_phase3.py` + `test_session_phase3.py` (2 passed); frontend typecheck + 52 unit + 62 E2E passed. Gaze ingestion thuộc Phase 4. |
| 4 | Hoàn tất lõi (protocol/ingestion/queue) | `gaze_ingest.py` (presentation/layout/batch idempotent), `services/gaze/app/protocol.py` + `test_protocol.py` (4 passed), `backend/tests/test_gaze_phase4.py` (1 passed), frontend `use-gaze-tracker` protocol v2 + `gaze-queue` IndexedDB + `gaze-sender`; typecheck + 52 unit + 62 E2E passed. |
| 5 | Hoàn tất (AOI/analytics/RAG/export) | `services/aoi.py`, `analysis.py`, `metrics.py`; routes `aoi.py`, `analytics.py`, `chat.py`, `chat_internal.py`; chatbot ingest/retrieval versioned; `backend/tests/test_aoi_phase5.py` + `test_chat_phase5.py` (3 passed); chatbot tests 89 passed; frontend typecheck + 52 unit + 62 E2E passed; chatbot role không đọc được `quiz_specs`/`users`/`quiz_attempts` |
| 6 | Hoàn tất | `docs/test-evidence/phase6-rebuild.txt` (schema/seed identical sau 2 lần rebuild, DB khác không đổi); `phase6-smoke.txt` (course→publish→enroll→calibration→session→gaze→AOI→analysis→heatmap→export→chat access); `phase6-worker-recovery.txt`; `phase6-redis-fallback.txt`; `phase6-export-stream.txt`; `phase6-load.log` (2.000 samples/s × 30 phút = 3.600.000 samples, p50 136ms, p95 219ms, max 277ms, DB ~970MB); backend 63 passed, chatbot 89 passed, frontend 52 unit + 62 E2E, typecheck pass |

### 5.5. Kiểm thử bắt buộc

**Database và reset**

- Reset guard từ chối Docker remote, project khác, DB sai tên và database hệ thống.
- Rebuild DB test riêng hai lần cho cùng schema/reference seed.
- Database khác, R2 objects và shared volumes không thay đổi.
- ORM metadata khớp FK, CHECK, UNIQUE, indexes trong catalog.
- Trigger từ chối sửa/xóa published revision, asset đang tham chiếu và submitted attempt.
- App/chatbot roles có đúng quyền; chatbot không SELECT được quiz specs.

**Content và quiz**

- Publish trong lúc sinh viên đang học/làm bài.
- Xóa một/nhiều slide, thay PDF, reorder, xóa chương và archive course.
- Đọc lại đúng ảnh/đề cũ qua history.
- Hai giáo viên sửa/publish đồng thời.
- Upload/render/commit lỗi không làm hỏng version đang published.
- Double start/submit/retry không tạo trạng thái trùng.
- Sửa deadline/đáp án không thay đổi attempt đã bắt đầu.

**Gaze và AOI**

- Inference trả về sau đổi slide.
- Scroll, chat animation, image load, zoom và session đổi nhưng geometry giống nhau.
- Observer không bị gaze-dot làm starvation.
- Snapshot response cũ không ghi đè generation mới.
- Mất mạng, mất ACK, 429, batch sai thứ tự, nhiều tab và nhiều người chung NAT.
- No-face/offscreen/error vẫn được ghi đúng.
- AOI chồng lấn, letterboxing, ancestor clipping và layout thiếu.
- Rebuild theo time range không thay dữ liệu ngoài scope/run.
- Cùng raw, watermark, AOI set và algorithm cho cùng kết quả.

**Analytics và RAG**

- Không trộn V1/V2 hoặc các attempts.
- Reorder không tái tạo embedding.
- Vector/keyword retrieval loại draft và version ngoài context trước top-k.
- History citation resolve đúng asset.
- Attempt đã nộp cũ không vượt restriction của attempt mới.
- Cache invalidation giữa compute/write không tạo kết quả stale.

**Vận hành**

- Worker restart không mất công việc đã ghi DB.
- Redis unavailable không mất raw đã ACK.
- Partition tháng mới/default hoạt động.
- Export lớn không tải toàn bộ dataset vào RAM.
- Load test synthetic ingestion: 2.000 samples/s trong 30 phút, cùng lớp học chung NAT; không mất hoặc trùng batch đã ACK.
- Đo riêng throughput inference thực tế trên GPU hiện tại.

### 5.6. Checklist sau rebuild

1. Database chỉ có schema baseline mới và migration tracking mới.
2. Không còn bảng/cột legacy trong danh mục loại bỏ.
3. Reference seed chạy lặp không tạo trùng; dev seed không ghi đè mật khẩu đã đổi.
4. Tạo khóa → chương → bài/quiz → upload → publish thành công.
5. Sinh viên học/làm bài và thu gaze/AOI thành công.
6. Giáo viên sửa/xóa/publish khi có phiên đang chạy; lịch sử vẫn đối chiếu được.
7. Retry quiz giữ các lượt trước.
8. Rebuild AOI, heatmap và export xác minh được bằng manifest/version IDs.
9. Restart stack không mất raw, attempts hoặc trạng thái job.
10. Ghi lại kết quả test và cấu hình máy; chỉ đánh dấu phase hoàn tất khi đạt gate.

**Ngoài V1:** event sourcing, ngân hàng câu hỏi độc lập, polygon AOI, tự chuyển AOI giữa hai ảnh khác nhau, lưu video, cold storage và tự động purge dữ liệu nghiên cứu.

**Điểm dừng:** Phase 0–6 đã triển khai và nghiệm thu trên development. Baseline checksum đã khóa; mọi thay đổi schema sau đây phải là migration mới. Các hạn chế còn lại: benchmark inference GPU thực tế chưa chạy trong môi trường này; load test đo ingestion/ACK/DB, không chứng minh GPU đủ cho cùng số người; R2/local media cũ được giữ nguyên, không xóa bucket/volume.
