# Phase 0 — Schema catalog đích

Danh mục này là hợp đồng giữa `db/migrations/001_baseline.sql` và ORM. Mọi
thay đổi sau Phase 6 phải là migration mới, không sửa baseline đã khóa checksum.

## 1. Nguyên tắc

- PostgreSQL 16, extension `vector` và `unaccent`; không cài `pg_trgm`.
- UUID dùng `gen_random_uuid()`.
- Bảng lịch sử/version không có `ON DELETE CASCADE` từ identity sang version đã
  publish; chỉ draft/join table được cascade.
- Composite FK cho các cặp `(id, parent_id)`; trigger cho quan hệ chéo.
- Không dùng `CHECK` chứa truy vấn bảng khác.

## 2. Bảng và cột

### 2.1 Identity/auth

| Bảng | Cột chính | Ràng buộc |
|---|---|---|
| `users` | `id`, `email`, `password_hash`, `status`, `last_login_at`, `created_at`, `updated_at`, `deleted_at`, `must_change_password` | `status IN ('active','suspended','banned')`; unique `lower(email)` |
| `roles` | `id SMALLSERIAL`, `code`, `label` | unique `code` |
| `user_roles` | `user_id`, `role_id`, `granted_at` | PK `(user_id, role_id)` |
| `auth_sessions` | `id`, `user_id`, `refresh_token_hash`, `user_agent`, `ip_address`, `expires_at`, `revoked_at`, `created_at` | unique `refresh_token_hash`; index `user_id` |
| `user_profiles` | `user_id`, `full_name`, `date_of_birth`, `gender`, `phone`, `avatar_url`, `updated_at` | `gender IN ('male','female','other')` |
| `student_profiles` | `user_id`, `student_code`, `program` | unique `student_code` |
| `teacher_profiles` | `user_id`, `teacher_code`, `department` | unique `teacher_code` |
| `course_teachers` | `course_id`, `teacher_id`, `assigned_by`, `assigned_at` | PK `(course_id, teacher_id)` |

### 2.2 Media/assets

| Bảng | Cột chính | Ràng buộc |
|---|---|---|
| `media_assets` | `id`, `course_id`, `storage_backend`, `object_key`, `sha256`, `mime_type`, `byte_size`, `image_width`, `image_height`, `state`, `created_at` | `storage_backend IN ('local','r2')`; `state IN ('staging','ready','failed','deleted')`; unique `(course_id, sha256)`, `(storage_backend, object_key)` |
| `slide_documents` | `slide_version_id`, `pipeline_version`, `model_version`, `transcript`, `embedding vector(1024)`, `content_tsv`, `ingestion_state`, `ingestion_error`, `created_at`, `updated_at` | PK/FK `slide_version_id`; `ingestion_state IN ('pending','ready','failed')`; HNSW cosine; GIN FTS |

### 2.3 Content

| Bảng | Cột chính | Ràng buộc |
|---|---|---|
| `courses` | `id`, `owner_id`, `created_by`, `archived_at`, `show_gaze_dot`, `require_calibration`, `published_version_id`, `created_at`, `updated_at` | FK owner/created_by; FK published_version deferrable |
| `course_versions` | `id`, `course_id`, `version_no`, `state`, `generation`, `title`, `description`, `thumbnail_asset_id`, `created_by`, `created_at`, `published_at`, `published_by` | `state IN ('draft','published','archived')`; unique `(course_id, version_no)`; partial unique một draft/course |
| `course_version_modules` | `id`, `course_version_id`, `module_key`, `title`, `position` | unique `(course_version_id, position)`, `(course_version_id, module_key)` |
| `lessons` | `id`, `course_id`, `kind`, `created_at` | `kind IN ('lesson','quiz')` |
| `lesson_versions` | `id`, `lesson_id`, `version_no`, `state`, `title`, `created_by`, `created_at`, `published_at`, `published_by` | unique `(lesson_id, version_no)`; partial unique một draft/lesson |
| `course_version_items` | `id`, `course_version_id`, `module_id`, `lesson_id`, `lesson_version_id`, `position` | unique `(course_version_id, position)`, `(course_version_id, lesson_id)`; composite FK module/version |
| `slides` | `id`, `lesson_id`, `created_at` | FK lesson |
| `slide_versions` | `id`, `slide_id`, `revision_no`, `image_asset_id`, `source_pdf_asset_id`, `source_page`, `render_metadata`, `created_by`, `created_at` | unique `(slide_id, revision_no)`; FK asset RESTRICT |
| `lesson_version_slides` | `id`, `lesson_version_id`, `slide_id`, `slide_version_id`, `position`, `title`, `is_key` | unique `(lesson_version_id, position)`, `(lesson_version_id, slide_id)`; composite FK slide version |
| `content_audit_events` | `id`, `actor_id`, `course_id`, `course_version_id`, `action`, `request_id`, `created_at` | `action IN ('publish','archive','restore')` |

### 2.4 Quiz

| Bảng | Cột chính | Ràng buộc |
|---|---|---|
| `quiz_specs` | `lesson_version_id`, `instructions`, `duration_minutes`, `due_at`, `allow_retry`, `allow_chatbot`, `questions`, `created_at`, `updated_at` | PK/FK lesson_version; `duration_minutes > 0`; `jsonb_typeof(questions)='array'` |
| `quiz_attempts` | `id`, `enrollment_id`, `course_version_item_id`, `lesson_id`, `attempt_no`, `status`, `started_at`, `expires_at`, `submitted_at`, `answers`, `grading`, `score`, `max_score` | unique `(enrollment_id, lesson_id, attempt_no)`; partial unique một `in_progress`; `status IN ('in_progress','submitted','expired')` |

### 2.5 Calibration/session/gaze

| Bảng | Cột chính | Ràng buộc |
|---|---|---|
| `devices` | `id`, `owner_id`, `fingerprint`, `current_calibration_id`, `created_at` | unique `(owner_id, fingerprint)`; FK calibration deferrable |
| `calibrations` | `id`, `device_id`, `model_ubj`, `model_hash`, `model_version`, `mae_px`, `viewport_width_px`, `viewport_height_px`, `device_pixel_ratio`, `config`, `created_at` | immutable; `mae_px >= 0`; viewport > 0 |
| `calibration_settings` | `id=1`, `enabled`, `threshold`, `updated_at`, `updated_by` | `threshold BETWEEN 0.01 AND 0.30` |
| `learning_sessions` | `id`, `enrollment_id`, `course_version_item_id`, `quiz_attempt_id`, `calibration_id`, `pipeline_version`, `config`, `tracking_consent`, `status`, `started_at`, `ended_at`, `expires_at`, `clock_uncertainty_ms` | `status IN ('in_progress','completed','aborted','expired')` |
| `content_presentations` | `id`, `session_id`, `lesson_version_slide_id`, `surface`, `sequence_no`, `started_at`, `ended_at` | unique `(session_id, sequence_no)`; `surface IN ('lesson','quiz')` |
| `gaze_batches` | `id`, `session_id`, `presentation_id`, `layout_snapshot_id`, `batch_id`, `batch_no`, `sequence_start`, `sequence_end`, `payload_hash`, `received_at`, `received_count`, `stored_count`, `duplicate_count`, `rejected_count` | unique `(session_id, batch_id)`, `(session_id, batch_no)`; `sequence_end >= sequence_start` |
| `gaze_samples` | `id BIGSERIAL`, `session_id`, `batch_id`, `sequence`, `capture_monotonic_ns`, `event_time`, `viewport_x`, `viewport_y`, `status`, `quality_flags` | PK `(id, event_time)`; partition theo tháng; composite FK batch/session; status/coordinate CHECK |

### 2.6 AOI/analysis/metrics/chat

| Bảng | Cột chính | Ràng buộc |
|---|---|---|
| `aoi_sets` | `id`, `scope`, `slide_version_id`, `ui_schema_version`, `revision`, `state`, `created_by`, `created_at`, `published_at` | `scope IN ('slide','ui')`; `state IN ('draft','published','archived')`; partial unique published |
| `aoi_definitions` | `id`, `aoi_set_id`, `code`, `name`, `parent_id`, `geometry` | unique `(aoi_set_id, code)`; parent cùng set (trigger) |
| `aoi_layout_snapshots` | `id`, `presentation_id`, `ui_aoi_set_id`, `captured_at`, `sequence_no`, `layout_generation`, `image_transform` | unique `(presentation_id, layout_generation)` |
| `aoi_layout_rects` | `id BIGSERIAL`, `snapshot_id`, `semantic_code`, `element_key`, `x_min`, `y_min`, `x_max`, `y_max` | order/bounds CHECK |
| `analysis_runs` | `id`, `session_id`, `aoi_set_id`, `from_time`, `to_time`, `batch_watermark`, `algorithm_version`, `config`, `status`, `error`, `created_at`, `completed_at` | `to_time > from_time`; `status IN ('pending','running','completed','failed')` |
| `aoi_hits` | `run_id`, `sample_id`, `event_time`, `definition_id` | PK `(run_id, sample_id, event_time, definition_id)`; composite FK sample |
| `presentation_metrics` | `presentation_id`, `algorithm_version`, `batch_watermark`, `sample_count`, `on_slide_count`, `dwell_ms`, `fixation_count`, `heatmap_grid`, `computed_at` | PK `(presentation_id, algorithm_version)` |
| `chat_sessions` | `id`, `student_id`, `course_id`, `course_version_id`, `lesson_id`, `lesson_version_id`, `quiz_attempt_id`, `title`, `context_key`, `created_at`, `updated_at`, `archived_at` | FK context; index student/course/updated |
| `chat_messages` | `id`, `session_id`, `role`, `content`, `citations`, `intent`, `created_at` | `role IN ('student','assistant')`; citations array |
| `app_metadata` | `key`, `value`, `updated_at` | PK `key` |
| `schema_migrations` | `filename`, `checksum`, `applied_at`, `duration_ms` | PK `filename` |

## 3. View

| View | Mục đích |
|---|---|
| `v_published_course_outline` | Outline published: course → version → module → item → lesson version → slide version → asset |
| `v_chatbot_slide_documents` | Tài liệu published cho RAG: transcript, embedding, FTS, citation IDs; không chứa quiz/users |
| `v_session_metrics` | Tổng hợp sample/dwell theo session, presentation, lesson version |
| `v_lesson_version_metrics` | Coverage/mastery theo enrollment + lesson version, dùng `is_key` |
| `v_class_heatmap` | Cộng heatmap grid theo course version + lesson version + slide version |

## 4. Cột immutable và transition

| Bảng | Immutable | Transition được phép |
|---|---|---|
| `course_versions` | Sau `state='published'`: title, description, thumbnail, modules/items | `draft → published`, `published → archived`; không sửa published |
| `lesson_versions` | Sau `state='published'`: title, slides, quiz spec | `draft → published`, `published → archived` |
| `slide_versions` | Toàn bộ sau INSERT | Không update/delete |
| `media_assets` | `object_key`, `sha256`, `mime_type`, `byte_size`, dimensions sau `state='ready'` | `staging → ready/failed`, `ready → deleted` chỉ khi orphan |
| `calibrations` | Toàn bộ sau INSERT | Không update/delete |
| `quiz_attempts` | `answers`, `grading`, `score`, `max_score`, `submitted_at` sau `submitted` | `in_progress → submitted/expired`; retry tạo attempt mới |
| `gaze_samples` | Toàn bộ sau INSERT | Không update/delete |
| `aoi_sets` | Sau `state='published'`: definitions | `draft → published`, `published → archived` |
| `analysis_runs` | Kết quả `completed` | `pending → running → completed/failed`; retry chỉ sửa run chưa xong |

## 5. Trigger bắt buộc

1. `trg_course_versions_immutable` — chặn sửa/xóa version published.
2. `trg_lesson_versions_immutable` — chặn sửa/xóa lesson version published.
3. `trg_slide_versions_immutable` — chặn update/delete slide version.
4. `trg_media_assets_immutable` — chặn đổi binary metadata khi ready.
5. `trg_calibrations_immutable` — chặn update/delete calibration.
6. `trg_quiz_attempts_submitted_immutable` — chặn sửa/xóa attempt submitted.
7. `trg_course_version_item_consistency` — module cùng course version, lesson cùng course, lesson version cùng lesson.
8. `trg_lesson_version_slide_consistency` — slide version cùng slide, slide cùng lesson.
9. `trg_quiz_attempt_consistency` — item cùng enrollment/course, lesson khớp item.
10. `trg_learning_session_consistency` — item cùng enrollment/course, attempt cùng enrollment/item, calibration cùng student.
11. `trg_presentation_consistency` — slide membership cùng lesson version của session.
12. `trg_gaze_batch_consistency` — presentation cùng session, layout cùng presentation.
13. `trg_aoi_definition_parent` — parent cùng aoi set.
14. `trg_aoi_hit_consistency` — definition cùng aoi set của run.
15. `trg_course_published_pointer` — published version cùng course và state published.
16. `trg_device_current_calibration` — calibration cùng device.
17. `trg_chat_session_context` — course version/lesson version/attempt cùng course/student.
18. `trg_analysis_run_scope` — slide AOI set thuộc lesson version của session.

## 6. Partition

- `gaze_samples` partition theo tháng `event_time`.
- PK `(id, event_time)`.
- Index `(session_id, event_time)`, `(batch_id, event_time)`.
- Default partition + tháng trước/current/3 tháng tới.
- Function `create_gaze_sample_partitions(months_ahead INT DEFAULT 3)`.
- Không tạo UNIQUE chỉ `(session_id, sequence)` trên bảng partition.
