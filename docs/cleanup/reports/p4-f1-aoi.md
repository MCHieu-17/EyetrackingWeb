# P4-F1 — AOI component split

## Summary

Tách các module AOI lớn thành các file nhỏ hơn mà không đổi hành vi, props hay
public export:

- `aoi-panel.tsx` (996 dòng) → thư mục `aoi-panel/` gồm `index.tsx` và các
  component con `aoi-row`, `group-section`, `help-dialog`, `no-label-row`.
- `aoi-overlay.tsx` → các helper hình học thuần chuyển sang
  `lib/aoi/geometry.ts`; `AoiOverlay` vẫn nằm trong `aoi-overlay.tsx` với
  props/export không đổi. `AoiRect` được re-export từ `aoi-overlay.tsx` để
  giữ nguyên public export cũ.
- Màu vùng trùng lặp ở panel/overlay → `lib/aoi/colors.ts` (`colorFor`).
- Các helper thuần của `use-aoi-editor.ts` → `lib/aoi/editor-helpers.ts`;
  `useAoiEditor` và return shape giữ nguyên.
- Thêm test Vitest cho `colors`, `geometry`, `editor-helpers`.

Không thay đổi file ngoài ownership. Không sửa API, schema, hay UI component
dùng chung.

## Files changed

### New

| File | Nội dung |
|---|---|
| `frontend/components/teacher/aoi/aoi-panel/index.tsx` | `AoiPanel` (props giữ nguyên), header, tab, danh sách, dialog tạo lại gợi ý |
| `frontend/components/teacher/aoi/aoi-panel/aoi-row.tsx` | `AoiRow` |
| `frontend/components/teacher/aoi/aoi-panel/group-section.tsx` | `GroupSection` |
| `frontend/components/teacher/aoi/aoi-panel/help-dialog.tsx` | `HelpDialog` |
| `frontend/components/teacher/aoi/aoi-panel/no-label-row.tsx` | `NoLabelRow` |
| `frontend/lib/aoi/colors.ts` | `colorFor(code)` dùng chung |
| `frontend/lib/aoi/geometry.ts` | `AoiRect`, `Box`, `Draft`, `numberValue`, `clamp01`, `normalizeRect`, `screenBox`, `measureElements`, `measureSlide`, `findAnchor`, `relativeRect` |
| `frontend/lib/aoi/editor-helpers.ts` | `pickLatest`, `toInputs`, `nextCustomCode`, `nextUiCustomCode`, `countCustom` |
| `frontend/lib/aoi/colors.test.ts` | Test màu ổn định/khác nhau |
| `frontend/lib/aoi/geometry.test.ts` | Test `clamp01`, `normalizeRect`, `screenBox`, `relativeRect`, `numberValue` |
| `frontend/lib/aoi/editor-helpers.test.ts` | Test các helper của editor |

### Modified

| File | Thay đổi |
|---|---|
| `frontend/components/teacher/aoi/aoi-overlay.tsx` | Import helper từ `lib/aoi/geometry`, `colorFor` từ `lib/aoi/colors`; xoá bản sao local; re-export `AoiRect` |
| `frontend/components/teacher/aoi/use-aoi-editor.ts` | Import helper từ `lib/aoi/editor-helpers`; xoá bản sao local |

### Deleted

| File | Lý do |
|---|---|
| `frontend/components/teacher/aoi/aoi-panel.tsx` | Thay bằng `aoi-panel/index.tsx`; import `./aoi-panel` của `aoi-workspace.tsx` tự resolve sang thư mục, không cần sửa |

## Behavior preservation

- Body của `AoiPanel`, `AoiOverlay`, `useAoiEditor` được so khớp với bản gốc
  bằng `diff` sau khi tách: không có khác biệt (ngoài import/export).
- Các component con `AoiRow`, `GroupSection`, `NoLabelRow`, `HelpDialog` giữ
  nguyên JSX/logic; chỉ thêm `export` và đổi `React.ReactNode` →
  `ReactNode` (tương đương).
- Các helper hình học và editor helper giữ nguyên công thức/logic; chỉ thêm
  `export`.
- `AoiPanel` vẫn export từ `./aoi-panel` với cùng props.
- `AoiOverlay` vẫn export từ `./aoi-overlay` với cùng props; `AoiRect` vẫn
  export được từ module cũ.

## Tests run

Chạy trong `frontend/`:

```text
npm run lint       → pass (không có output lỗi)
npm run typecheck  → pass (tsc --noEmit)
npm run test       → 10 test files passed, 105 tests passed
npm run knip       → pass
```

Chi tiết `npm run test`:

```text
Test Files  10 passed (10)
     Tests  105 passed (105)
  Duration  1.61s
```

Trước thay đổi baseline là 7 test files / 73 tests; sau thay đổi thêm 3 test
files / 32 tests.

### Build note

`npm run build` (Turbopack mặc định) lỗi do môi trường worktree:

```text
Symlink [project]/node_modules is invalid, it points out of the filesystem root
```

`frontend/node_modules` là symlink trỏ về repo chính, nằm ngoài filesystem
root của Turbopack. Đây là vấn đề setup worktree, không phải lỗi code.
`npm run build -- --webpack` chạy thành công (13/13 static pages, đủ route).

## Risks

- Thấp: thay đổi thuần di chuyển code, không đổi logic.
- `aoi-panel/index.tsx` vẫn còn ~709 dòng; có thể tách tiếp danh sách
  slide/UI nếu cần, nhưng nằm ngoài phạm vi task này.
- `AoiRect` trong `lib/aoi/geometry.ts` trùng tên với `AoiRect` trong
  `lib/api/aoi.ts` (khác shape: một bên không có `code`). Đây là tình trạng
  sẵn có; task giữ nguyên để không đổi public type.
- Turbopack build trong worktree cần node_modules thật hoặc cấu hình
  `root` phù hợp; không ảnh hưởng lint/typecheck/test/knip.

## Follow-ups

- Có thể tách `renderSlideList` / `renderUiList` khỏi `aoi-panel/index.tsx`
  thành `slide-list.tsx` / `ui-list.tsx` ở task sau nếu muốn giảm thêm kích
  thước file.
- Có thể thêm test cho `measureElements`, `measureSlide`, `findAnchor` nếu
  muốn phủ đầy đủ các helper hình học.
- Cân nhắc thống nhất `AoiRect` giữa `lib/api/aoi.ts` và
  `lib/aoi/geometry.ts` trong một task riêng (cần đổi type public nên không
  làm ở đây).
