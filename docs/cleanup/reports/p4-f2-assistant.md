# P4-F2 — Assistant component split

## Summary

Tách `frontend/components/assistant/study-assistant-chat.tsx` (768 dòng) thành
thư mục `study-assistant-chat/` gồm các module nhỏ, không đổi hành vi, props
hay public export:

- `index.tsx` — `StudyAssistantChat` với đúng props `{ courseId, open, onClose }`,
  giữ toàn bộ state/effect/hook và luồng gửi tin.
- `panel-header.tsx` — header panel (tiêu đề, phụ đề theo mode, menu phiên, nút đóng).
- `message-list.tsx` — vùng cuộn, empty state + gợi ý, danh sách message, lỗi, bottom anchor.
- `message-bubble.tsx` — một message (student/assistant, pending/streaming, citations).
- `composer.tsx` — form nhập câu hỏi, auto-resize textarea, Enter/Shift+Enter.
- `citation-list.tsx` — chip trích dẫn và dialog xem nguồn (PDF/snippet).
- `session-list.tsx` — menu lịch sử phiên, dialog đổi tên, dialog xoá phiên.
- `markdown.tsx` — `Markdown` memoized + `MARKDOWN_CLASS`, giữ nguyên plugin
  `remark-gfm`, `remark-math`, `rehype-katex`, `remarkCitations`, `normalizeMath`.
- `chat-helpers.ts` — helper thuần: storage key, chọn phiên hiệu lực, map message
  server → UI, format citation, status label, subtitle/empty state theo mode,
  scroll-near-bottom, chọn phiên kế tiếp sau xoá, chuẩn hoá tiêu đề, format lỗi chat.
- `chat-helpers.test.ts` — 33 test Vitest cho các helper trên.

`lazy-study-assistant-chat.tsx` không cần sửa: import
`@/components/assistant/study-assistant-chat` tự resolve sang
`study-assistant-chat/index.tsx`.

Không thay đổi file ngoài ownership. Không sửa API, schema, UI component dùng
chung, hay `lazy-study-assistant-chat.tsx`.

## Files changed

### New

| File | Nội dung |
|---|---|
| `frontend/components/assistant/study-assistant-chat/index.tsx` | `StudyAssistantChat` (props giữ nguyên), state/effect/send flow |
| `frontend/components/assistant/study-assistant-chat/panel-header.tsx` | `AssistantHeader` |
| `frontend/components/assistant/study-assistant-chat/message-list.tsx` | `MessageList` + empty state |
| `frontend/components/assistant/study-assistant-chat/message-bubble.tsx` | `MessageBubble` |
| `frontend/components/assistant/study-assistant-chat/composer.tsx` | `Composer` |
| `frontend/components/assistant/study-assistant-chat/citation-list.tsx` | `CitationList`, `CitationDialog` |
| `frontend/components/assistant/study-assistant-chat/session-list.tsx` | `SessionMenu`, `RenameSessionDialog`, `DeleteSessionDialog` |
| `frontend/components/assistant/study-assistant-chat/markdown.tsx` | `Markdown` |
| `frontend/components/assistant/study-assistant-chat/chat-helpers.ts` | Helper thuần dùng chung |
| `frontend/components/assistant/study-assistant-chat/chat-helpers.test.ts` | Test Vitest cho helper |

### Deleted

| File | Lý do |
|---|---|
| `frontend/components/assistant/study-assistant-chat.tsx` | Thay bằng `study-assistant-chat/index.tsx`; import cũ tự resolve sang thư mục |

## Behavior preservation

- JSX của panel, header, message, citation chip/dialog, session menu/dialog và
  composer được giữ nguyên cấu trúc, `data-aoi`, `data-aoi-instance`, class và
  thứ tự phần tử.
- `StudyAssistantChat` vẫn export từ module `@/components/assistant/study-assistant-chat`
  với đúng props `courseId: string`, `open: boolean`, `onClose: () => void`.
- Logic state/effect/hook trong `index.tsx` giữ nguyên thứ tự và điều kiện:
  storage key, chọn phiên hiệu lực, đồng bộ message từ server, focus input,
  auto-scroll, Escape đóng panel, abort stream, optimistic message, xử lý lỗi
  429 và lỗi kết nối.
- Các helper chỉ chuyển logic thuần ra khỏi component, không đổi công thức:
  - `buildChatStorageKey` giữ nguyên format
    `study-chat:<user>:<course>:<assignment|reader>:<attempt|no-attempt>:<mode>`.
  - `resolveEffectiveSessionId` giữ nguyên quy tắc `undefined` → phiên gần nhất,
    `null` → phiên mới, phiên `canContinue === false` → fallback.
  - `formatCitationLabel` / `formatCitationLocation` giữ nguyên text hiển thị.
  - `formatChatError` giữ nguyên thông báo 429 và fallback.
- `Markdown` vẫn là `memo`; CSS `katex/dist/katex.min.css` vẫn được import
  trong module markdown nên bundle chat vẫn tải CSS như cũ.

## Tests run

Chạy trong `frontend/`:

```text
npm run lint       → pass (không có output lỗi)
npm run typecheck  → pass (tsc --noEmit)
npm run test       → 11 test files passed, 138 tests passed
npm run knip       → pass
```

Chi tiết `npm run test`:

```text
Test Files  11 passed (11)
     Tests  138 passed (138)
  Duration  1.42s
```

Trước thay đổi baseline là 7 test files / 73 tests; sau thay đổi thêm 1 test
file / 33 tests cho riêng task này (các test khác đến từ các task wave trước).

### Build note

`npm run build` (Turbopack mặc định) lỗi do môi trường worktree:

```text
Symlink [project]/node_modules is invalid, it points out of the filesystem root
```

`frontend/node_modules` là symlink trỏ về repo chính, nằm ngoài filesystem
root của Turbopack. Đây là vấn đề setup worktree, không phải lỗi code.
`npm run build -- --webpack` chạy thành công (13/13 static pages, đủ route),
xác nhận dynamic import `study-assistant-chat` → `study-assistant-chat/index.tsx`
resolve đúng.

## Risks

- Thấp: thay đổi thuần di chuyển code + tách helper, không đổi logic.
- `index.tsx` vẫn còn ~370 dòng vì giữ toàn bộ state/effect/send flow; có thể
  tách tiếp `use-study-assistant-chat.ts` nếu muốn, nhưng nằm ngoài phạm vi
  task này và dễ làm thay đổi thứ tự hook.
- `MessageList` tính `getEmptyState(mode)` mỗi render (kể cả khi không empty);
  chi phí không đáng kể (mảng 3 phần tử), không ảnh hưởng hành vi.
- `DialogDescription` của citation dialog render một text node thay vì hai text
  node như bản gốc; nội dung hiển thị giống hệt, không đổi cấu trúc element.
- Turbopack build trong worktree cần node_modules thật hoặc cấu hình `root`
  phù hợp; không ảnh hưởng lint/typecheck/test/knip.

## Follow-ups

- Có thể tách `use-study-assistant-chat.ts` (state + send flow) khỏi `index.tsx`
  ở task sau nếu muốn giảm thêm kích thước file, cần giữ nguyên thứ tự hook.
- Có thể thêm component test cho `StudyAssistantChat` (mock `use-chat`) để phủ
  luồng gửi/nhận stream; hiện task chỉ yêu cầu test helper thuần.
- Có thể dùng chung `ChatSessionLike` với type session trong `lib/api/chat.ts`
  nếu sau này type đó được export; hiện giữ type structural local để không
  sửa file ngoài ownership.
