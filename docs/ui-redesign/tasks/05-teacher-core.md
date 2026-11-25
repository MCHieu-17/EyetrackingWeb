# Task 05 — Khu giáo viên: danh sách, workspace, thông tin, học viên, cài đặt

## Phạm vi
`frontend/components/teacher/teacher-course-list.tsx`, `course-workspace.tsx`, `workspace-ui.tsx`, `course-info-tab.tsx`, `course-toggle.tsx`, `course-settings-section.tsx`, `calibration-toggle.tsx`, `camera-preview-toggle.tsx`, `gaze-dot-toggle.tsx`, `unsaved-guard.tsx`, `frontend/components/teacher/students-tab/*.tsx`.

## Việc cần làm
- `course-workspace.tsx`: header sticky `bg-background/85 backdrop-blur-md border-b border-border`; thanh tab dạng segmented `bg-muted rounded-full p-1`, tab active `bg-card text-primary shadow-xs` (giữ chúng là **link** như hiện tại, giữ nhãn "Nội dung", "Thông tin", "Học viên", "Vùng phân tích", "Trực quan hoá").
- Danh sách khoá học: card hàng có hover nâng nhẹ (`hover:border-primary/30 hover:shadow-md`), icon box `bg-accent text-accent-foreground`, badge "Đã xuất bản" success, "Nháp" muted.
- Students tab: bảng/summary/sheet chi tiết dùng token; số liệu nổi bật `font-display text-foreground`.
- Toggle/settings: dùng Switch từ `components/ui/switch` như hiện tại, chỉ đổi màu.
- Thay toàn bộ hex theo PLAN §1.

## Giữ nguyên
Nhãn "Tạo khóa học", "Thêm học viên", switch label, chữ toast, `#new-course-title`, `#new-course-description`.

## Kiểm tra trước khi báo xong
```bash
cd frontend && npm run lint && npm run typecheck
grep -rnE "\[#[0-9a-fA-F]{3,8}\]" <các file trong phạm vi>   # phải rỗng (trừ ngoại lệ PLAN §4)
git diff --stat                                              # chỉ file trong phạm vi
```
Đọc lại `docs/ui-redesign/PLAN.md` §3 (luật cứng) trước khi bắt đầu. Không commit.
