# P4-F4 — Teacher content editor / students split

## Summary

Tách các component lớn của giáo viên thành thư mục nhỏ hơn mà không đổi hành vi,
props hay public export:

- `lesson-quiz-editor.tsx` (563 dòng) → `lesson-quiz-editor/` gồm `index.tsx`
  (state/save/guard), `quiz-settings`, `question-list`, `question-preview`,
  `question-editor`, `save-bar`.
- `content-outline.tsx` (471 dòng) → `content-outline/` gồm `index.tsx`,
  `module-section`, `lesson-row`, `sortable-row`, `add-controls`,
  `inline-title-input`, `status-pill`.
- `content-editor.tsx` (476 dòng) → giữ `content-editor.tsx` làm orchestrator,
  tách `editor-header`, `delete-dialogs`, `publish-confirm-dialog` và helper
  thuần `editor-helpers.ts`.
- `lesson-editor.tsx` (401 dòng) → `lesson-editor/` gồm `index.tsx`,
  `upload-section`, `upload-alerts`, `slide-check-section`, `upload-helpers`.
- `students-tab.tsx` (480 dòng) → `students-tab/` gồm `index.tsx`,
  `students-summary`, `students-toolbar`, `students-table`, `student-row`,
  `add-student-dialog`, `student-detail-sheet`; helper thuần
  `students-helpers.ts`.
- `course-workspace.tsx`: lazy-load `ContentEditor`, `CourseInfoTab`,
  `StudentsTab` bằng `next/dynamic` với fallback `TabLoading`.
  `LazyAoiEditor` giữ nguyên import/props.

Không thay đổi API, schema, hay file ngoài ownership.

## Files changed

### New

| File | Nội dung |
|---|---|
| `frontend/components/teacher/content-editor/content-outline/index.tsx` | `ContentOutline` (props giữ nguyên), empty state, điều phối module |
| `frontend/components/teacher/content-editor/content-outline/module-section.tsx` | `ModuleSection`: header chương, DnD context, danh sách mục, nút thêm |
| `frontend/components/teacher/content-editor/content-outline/lesson-row.tsx` | `LessonRow`: dòng bài giảng/bài tập, đổi tên, xóa |
| `frontend/components/teacher/content-editor/content-outline/sortable-row.tsx` | `SortableRow`/`DragHandle` (chuyển từ file cũ) |
| `frontend/components/teacher/content-editor/content-outline/add-controls.tsx` | `AddItemMenu`, `AddModuleButton` |
| `frontend/components/teacher/content-editor/content-outline/inline-title-input.tsx` | `InlineTitleInput` |
| `frontend/components/teacher/content-editor/content-outline/status-pill.tsx` | `StatusPill`, `itemStatus` |
| `frontend/components/teacher/content-editor/lesson-quiz-editor/index.tsx` | `LessonQuizEditor` (props giữ nguyên), hydrate/save/guard |
| `frontend/components/teacher/content-editor/lesson-quiz-editor/quiz-settings.tsx` | `QuizSettings`: trạng thái, làm lại, chatbot, thời lượng/hạn/hướng dẫn |
| `frontend/components/teacher/content-editor/lesson-quiz-editor/question-list.tsx` | `QuestionList`: nút thêm + danh sách câu |
| `frontend/components/teacher/content-editor/lesson-quiz-editor/question-preview.tsx` | `QuestionPreview`: dòng xem nhanh câu hỏi |
| `frontend/components/teacher/content-editor/lesson-quiz-editor/question-editor.tsx` | `QuestionEditor`: khung câu đang chọn, compose `QuizQuestionEditor` dùng chung |
| `frontend/components/teacher/content-editor/lesson-quiz-editor/save-bar.tsx` | `SaveBar`: thanh lưu nháp/giao bài |
| `frontend/components/teacher/content-editor/lesson-editor/index.tsx` | `LessonEditor` (props giữ nguyên), state upload/index |
| `frontend/components/teacher/content-editor/lesson-editor/upload-section.tsx` | Khối tải tài liệu + vùng kéo thả |
| `frontend/components/teacher/content-editor/lesson-editor/upload-alerts.tsx` | Các alert success/error/pending/unindexed |
| `frontend/components/teacher/content-editor/lesson-editor/slide-check-section.tsx` | Khối kiểm tra tài liệu + `SlidePreview` |
| `frontend/components/teacher/content-editor/lesson-editor/upload-helpers.ts` | `UploadState`, `waitForImportJob` |
| `frontend/components/teacher/content-editor/editor-header.tsx` | `EditorHeader`: thống kê + nút xuất bản |
| `frontend/components/teacher/content-editor/delete-dialogs.tsx` | `DeleteModuleDialog`, `DeleteLessonDialog` |
| `frontend/components/teacher/content-editor/publish-confirm-dialog.tsx` | `PublishConfirmDialog` |
| `frontend/components/teacher/content-editor/editor-helpers.ts` | Helper thuần: đếm cây, tìm mục, validate slide, form quiz, thao tác câu hỏi |
| `frontend/components/teacher/content-editor/editor-helpers.test.ts` | 24 test cho helper |
| `frontend/components/teacher/students-helpers.ts` | Helper thuần: lọc/sắp xếp/đếm học viên, `relativeMinutes` |
| `frontend/components/teacher/students-helpers.test.ts` | 14 test cho helper |
| `frontend/components/teacher/students-tab/index.tsx` | `StudentsTab` (props giữ nguyên), data/state/remove |
| `frontend/components/teacher/students-tab/students-summary.tsx` | Header + thống kê + nút thêm |
| `frontend/components/teacher/students-tab/students-toolbar.tsx` | Tìm kiếm/xóa tìm kiếm |
| `frontend/components/teacher/students-tab/students-table.tsx` | Bảng + sort header |
| `frontend/components/teacher/students-tab/student-row.tsx` | Hàng học viên + row actions |
| `frontend/components/teacher/students-tab/add-student-dialog.tsx` | `AddStudentDialog` |
| `frontend/components/teacher/students-tab/student-detail-sheet.tsx` | Sheet chi tiết học viên |

### Modified

| File | Thay đổi |
|---|---|
| `frontend/components/teacher/content-editor/content-editor.tsx` | Dùng helper + component con; `ContentEditor` export/props giữ nguyên |
| `frontend/components/teacher/course-workspace.tsx` | `next/dynamic` cho 3 tab; `LazyAoiEditor` giữ nguyên |

### Deleted

| File | Lý do |
|---|---|
| `frontend/components/teacher/content-editor/content-outline.tsx` | Thay bằng `content-outline/index.tsx` |
| `frontend/components/teacher/content-editor/lesson-editor.tsx` | Thay bằng `lesson-editor/index.tsx` |
| `frontend/components/teacher/content-editor/lesson-quiz-editor.tsx` | Thay bằng `lesson-quiz-editor/index.tsx` |
| `frontend/components/teacher/content-editor/sortable-row.tsx` | Chuyển vào `content-outline/sortable-row.tsx` |
| `frontend/components/teacher/students-tab.tsx` | Thay bằng `students-tab/index.tsx` |

## Behavior preservation

- `ContentEditor`, `StudentsTab`, `CourseWorkspace` giữ nguyên tên export và
  props. Import `@/components/teacher/content-editor` và
  `@/components/teacher/students-tab` tự resolve sang `index.tsx` của thư mục.
- `LessonEditor`, `LessonQuizEditor`, `ContentOutline` giữ nguyên props; các
  component con chỉ nhận thêm callback/state cần thiết.
- Logic save/hydrate/guard của quiz, upload/index của lesson, lọc/sắp xếp/xóa
  học viên được giữ nguyên; helper thuần chỉ thay thế code tính toán tương ứng.
- `LazyAoiEditor` trong `course-workspace.tsx` không đổi import/props.
- Không có bulk action trong UI gốc của tab Học viên; vì vậy phần được tách là
  toolbar tìm kiếm + row actions, không thêm hành vi bulk mới.
- Option editing của bài tập vẫn nằm trong `QuizQuestionEditor` dùng chung
  (`components/quiz/**`, F3 sở hữu, không được sửa). `question-editor.tsx` chỉ
  compose component đó; không tạo bản sao để tránh lệch hành vi.

## Tests run

Chạy trong `frontend/`:

```text
npm run lint       → pass (không có output lỗi)
npm run typecheck  → pass (tsc --noEmit)
npm run test       → 12 test files passed, 143 tests passed
npm run knip       → pass
npm run build -- --webpack → pass (13/13 static pages)
```

Chi tiết `npm run test`:

```text
Test Files  12 passed (12)
     Tests  143 passed (143)
  Duration  1.71s
```

Baseline trước task (sau F1/F5): 10 test files / 105 tests. Task thêm 2 test
files / 38 tests cho `editor-helpers` và `students-helpers`.

## Risks

- Thấp: thay đổi chủ yếu là di chuyển code; logic được giữ nguyên và đã được
  typecheck/lint/test/knip xác nhận.
- `next/dynamic` với `ssr: false` làm tab Nội dung (tab mặc định) hiển thị
  fallback trong lần tải đầu thay vì render server; đây là mục tiêu lazy-load
  của task, không phải lỗi.
- `content-editor.tsx` vẫn còn ~434 dòng; có thể tách tiếp phần publish/checklist
  nếu muốn, nhưng nằm ngoài phạm vi task này.
- `lesson-quiz-editor/index.tsx` vẫn còn ~328 dòng do chứa state/save/guard;
  phần JSX đã được tách ra các component con.

## Follow-ups

- Có thể tách tiếp `content-editor.tsx` thành hook `use-content-editor` nếu
  muốn giảm thêm kích thước file.
- Có thể thêm test component (React Testing Library) cho `ContentOutline` và
  `StudentsTable` nếu muốn phủ hành vi UI, hiện chỉ test helper thuần.
- Cân nhắc thêm bulk actions thật cho tab Học viên ở task riêng (cần thay đổi
  hành vi/UI nên không làm trong task này).
- Có thể chuyển `waitForImportJob` sang test với fake timers nếu muốn phủ luồng
  poll job import.
