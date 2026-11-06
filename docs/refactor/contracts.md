# Phase 0 — API/schema contracts

Tài liệu này chốt contract trước khi thay consumer. Nó là nguồn tham chiếu cho
Phase 1–5; mọi thay đổi contract phải cập nhật file này và `PLAN.md`.

## 1. Route cũ → route mới

| Route cũ | Route mới | Consumer |
|---|---|---|
| `GET /teacher/courses` | giữ nguyên, response có `publishedVersionId`, `draftVersionId`, `generation` | `frontend/components/teacher/teacher-course-list.tsx` |
| `POST /teacher/courses` | giữ nguyên; tạo course + draft version đầu tiên | `frontend/components/teacher/content-editor/new-course-setup.tsx` |
| `GET /teacher/courses/{id}` | `GET /teacher/courses/{id}/draft` cho working tree; `GET /teacher/courses/{id}` trả metadata + published outline | `frontend/components/teacher/course-workspace.tsx` |
| `PATCH /teacher/courses/{id}` | `PATCH /teacher/courses/{id}` chỉ sửa metadata vận hành (archive, tracking, calibration); không dùng để publish | `course-settings-section.tsx` |
| `GET /teacher/courses/{id}/modules` | nằm trong `GET /teacher/courses/{id}/draft` | `content-outline.tsx` |
| `POST/PATCH/DELETE /teacher/modules...` | CRUD trong draft, nhận `expectedGeneration` | `content-editor.tsx` |
| `POST/PATCH/DELETE /teacher/lessons...` | CRUD trong draft, nhận `expectedGeneration` | `lesson-editor.tsx` |
| `POST /teacher/lessons/{id}/slides` | `POST /teacher/courses/{id}/draft/slides` (batch) | `lesson-editor.tsx` |
| `POST /teacher/courses/{id}/publish` | giữ nguyên; publish toàn khóa, trả `courseVersionId` | `publish-checklist.tsx` |
| `GET /teacher/courses/{id}/versions` | mới; danh sách version + history | `course-workspace.tsx` |
| `POST /teacher/courses/{id}/restore` | mới; tạo draft từ version được chọn | `course-workspace.tsx` |
| `GET /api/courses/{id}` | giữ nguyên; chỉ trả published version hiện hành | `frontend/components/courses/course-browser.tsx` |
| `GET /api/me/enrollments` | giữ nguyên; thêm `courseVersionId` | `frontend/components/student/student-home.tsx` |
| `POST /api/learning-sessions` | mới; thay `POST /api/gaze/sessions` | `frontend/hooks/use-gaze-tracker.ts` |
| `GET /api/learning-sessions/{id}/contents` | mới; nội dung đúng session đã cấp | `learning-reader.tsx` |
| `POST /api/lessons/{id}/attempts` | mới; thay `POST /api/assignments/{id}/start` | `frontend/hooks/use-quiz.ts` |
| `POST /api/attempts/{id}/submit` | mới; thay `POST /api/assignments/{id}/submit` | `frontend/hooks/use-quiz.ts` |
| `GET /api/lessons/{id}/attempts` | mới; lịch sử attempt | `frontend/components/quiz/inline-quiz.tsx` |
| `POST /api/learning-sessions/{id}/presentations` | mới | `learning-reader.tsx` |
| `POST /api/presentations/{id}/layouts` | mới; thay `POST /api/aoi/layouts` | `frontend/hooks/use-aoi-snapshot.ts` |
| `POST /api/learning-sessions/{id}/gaze-batches` | mới; thay `POST /api/gaze/raw` | `frontend/hooks/use-gaze-tracker.ts` |
| `POST /api/aoi/sets`, `POST /api/aoi/sets/{id}/publish` | mới; thay `POST /api/aoi/definitions` | `frontend/components/teacher/aoi-editor.tsx` |
| `POST /api/analysis-runs` | mới; thay `POST /api/aoi/rebuild` | `frontend/components/teacher/heatmap-viewer.tsx` |
| `GET /api/analysis-runs/{id}` | mới | `heatmap-viewer.tsx` |
| `GET /api/analysis-runs/{id}/export` | mới; streaming | `heatmap-viewer.tsx` |

Các route legacy bị xóa sau Phase 5, không giữ adapter.

## 2. DTO identity/version/membership

### Content

```text
CourseSummary
  id, title, description, thumbnailUrl, archivedAt,
  publishedVersionId, draftVersionId, generation,
  showGazeDot, requireCalibration, lessonCount, studentCount

CourseDraft
  courseId, courseVersionId, versionNo, generation, state,
  title, description, thumbnailAssetId,
  modules: [CourseVersionModule]

CourseVersionModule
  id, moduleKey, title, position,
  items: [CourseVersionItem]

CourseVersionItem
  id, lessonId, lessonVersionId, kind, title, position,
  slideCount, quiz: QuizSpecSummary | null

LessonVersion
  id, lessonId, versionNo, state, title,
  slides: [LessonVersionSlide]

LessonVersionSlide
  id, slideId, slideVersionId, position, title, isKey,
  imageAssetId, imageUrl, sourcePdfAssetId, sourcePage
```

### Quiz

```text
QuizSpec
  lessonVersionId, instructions, durationMinutes, dueAt,
  allowRetry, allowChatbot, questions: [Question]

Question
  id, prompt, options: [{id, text}], correctOptionIds: [id],
  points, multiple

QuizAttempt
  id, enrollmentId, courseVersionItemId, lessonId, attemptNo,
  status, startedAt, expiresAt, submittedAt,
  answers, grading, score, maxScore
```

### Session/gaze

```text
LearningSession
  id, enrollmentId, courseVersionItemId, quizAttemptId,
  calibrationId, pipelineVersion, status,
  startedAt, endedAt, expiresAt, trackingConsent

ContentPresentation
  id, sessionId, lessonVersionSlideId, surface,
  sequenceNo, startedAt, endedAt

GazeBatch
  id, sessionId, presentationId, layoutSnapshotId,
  batchId, batchNo, sequenceStart, sequenceEnd,
  payloadHash, receivedAt, receivedCount, storedCount,
  duplicateCount, rejectedCount

GazeSample
  id, sessionId, batchId, sequence, captureMonotonicNs,
  eventTime, viewportX, viewportY, status, qualityFlags
```

### AOI/analysis

```text
AoiSet
  id, scope, slideVersionId, uiSchemaVersion, revision,
  state, createdBy, createdAt, publishedAt

AoiDefinition
  id, aoiSetId, code, name, parentId, geometry

AnalysisRun
  id, sessionId, aoiSetId, fromTime, toTime,
  batchWatermark, algorithmVersion, status, error,
  createdAt, completedAt

PresentationMetric
  presentationId, algorithmVersion, batchWatermark,
  sampleCount, onSlideCount, dwellMs, fixationCount,
  heatmapGrid, computedAt
```

## 3. Error codes

| HTTP | `code` | Khi nào |
|---|---|---|
| 409 | `content_changed` | `expectedGeneration` không khớp generation hiện tại |
| 409 | `version_changed` | Version đã đổi giữa GET outline và POST start |
| 409 | `attempt_exists` | Đã có attempt `in_progress` cho enrollment/lesson |
| 409 | `attempt_submitted` | Submit lần hai hoặc sửa attempt đã nộp |
| 409 | `session_closed` | Resume/ingest vào session đã đóng |
| 409 | `session_expired` | Session quá hạn |
| 409 | `viewport_mismatch` | Viewport/calibration không khớp session |
| 409 | `batch_conflict` | Cùng `batchId` nhưng payload hash khác |
| 409 | `batch_out_of_order` | `batchNo`/sequence không đúng thứ tự |
| 409 | `content_not_published` | Học nội dung chưa publish |
| 409 | `quiz_not_ready` | Quiz thiếu câu hỏi/đáp án hợp lệ |
| 422 | `validation_error` | Dữ liệu không hợp lệ |
| 403 | `forbidden` | Không đủ quyền |
| 404 | `not_found` | Không tìm thấy hoặc không có quyền xem |

Mọi response lỗi giữ shape hiện tại:

```json
{"detail": {"code": "content_changed", "message": "..."}}
```

## 4. Generation và idempotency

- Mọi mutation draft nhận `expectedGeneration` (integer). Thiếu hoặc lệch → 409
  `content_changed`, không áp dụng một phần.
- `POST /teacher/courses/{id}/publish` nhận `expectedGeneration`; publish là một
  transaction, tăng generation một lần.
- `POST /api/lessons/{id}/attempts` nhận `Idempotency-Key` (UUID). Cùng key trả
  attempt cũ; khác payload → 409.
- `POST /api/learning-sessions/{id}/gaze-batches` nhận `batchId` (UUID) và
  `batchNo`. Cùng `batchId` + cùng `payloadHash` trả ACK cũ; khác hash → 409.
- `POST /api/learning-sessions/{id}/presentations` nhận `sequenceNo`; trùng
  sequence trả presentation cũ.
- `POST /api/analysis-runs` nhận `Idempotency-Key`; cùng key trả run cũ.

## 5. Consumer map

| Consumer | Contract |
|---|---|
| `frontend/lib/api/teacher.ts` | CourseDraft, CourseVersionModule, CourseVersionItem, LessonVersion, LessonVersionSlide |
| `frontend/lib/api/student.ts` | CourseSummary, CourseOutline, LearningSession, ContentPresentation |
| `frontend/lib/api/quiz.ts` | QuizSpec, QuizAttempt |
| `frontend/lib/api/calibration.ts` | Calibration, Device |
| `frontend/lib/api/aoi.ts` | AoiSet, AoiDefinition, AnalysisRun, PresentationMetric |
| `frontend/lib/api/chat.ts` | ChatSession, ChatMessage, citations |
| `services/chatbot/app/services/ingest.py` | `v_chatbot_slide_documents` |
| `services/chatbot/app/workflow/retrieval.py` | `v_chatbot_slide_documents` + version filters |
| `services/gaze/app/api/session.py` | frame metadata + JPEG protocol v2 |
| `backend/app/api/routes/gaze.py` | GazeBatch/GazeSample ingestion |
| `backend/app/api/routes/analytics.py` | `v_session_metrics`, `v_lesson_version_metrics`, `v_class_heatmap` |

## 6. Quy ước chung

- ID là UUID (trừ `gaze_samples.id` BIGSERIAL và các bảng join dùng composite PK).
- Thời gian là `TIMESTAMPTZ` UTC.
- Tọa độ viewport là `REAL`, gốc trên-trái, có thể ngoài `[0,1]`; no-face/error
  dùng `NULL`.
- Không trả `password_hash`, `model_ubj`, `refresh_token_hash` trong bất kỳ DTO.
- Không dùng `status` mutable để giả lập publish; publish là con trỏ version.
