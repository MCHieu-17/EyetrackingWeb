# Task 04 — Khu học viên (ngoài reader)

## Phạm vi
`frontend/components/student/student-home.tsx`, `frontend/components/student/preflight-check/*.tsx`, `frontend/components/courses/course-browser.tsx`, `frontend/components/profile/profile-page.tsx`, `frontend/components/display-guard/display-guard-overlay.tsx`.

## Việc cần làm
- Thay màu hardcode bằng token (PLAN §1).
- `course-browser.tsx` (bảng khoá học của học viên): hàng hover `hover:bg-muted/60`, icon box `bg-accent text-accent-foreground`, badge "Đang học" = `bg-success/10 text-success`, header bảng `text-muted-foreground` chữ hoa nhỏ. Thêm thanh tiến độ nhỏ nếu dữ liệu đã có sẵn trong props (không thêm API).
- Preflight: các bước kiểm tra camera dạng card `bg-card border-border rounded-2xl`; trạng thái OK/lỗi dùng token success/destructive kèm icon.
- Profile: card thông tin + avatar `bg-primary text-primary-foreground`.
- Display-guard overlay: nền `bg-background/95 backdrop-blur`, card trung tâm token.

## Cấm
Không đụng `components/student/learning-reader/**` (task 09).

## Kiểm tra trước khi báo xong
```bash
cd frontend && npm run lint && npm run typecheck
grep -rnE "\[#[0-9a-fA-F]{3,8}\]" <các file trong phạm vi>   # phải rỗng (trừ ngoại lệ PLAN §4)
git diff --stat                                              # chỉ file trong phạm vi
```
Đọc lại `docs/ui-redesign/PLAN.md` §3 (luật cứng) trước khi bắt đầu. Không commit.
