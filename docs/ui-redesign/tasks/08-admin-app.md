# Task 08 — Admin + trang lỗi/404 + quét còn sót ngoài reader

## Phạm vi
`frontend/components/admin/**`, `frontend/app/**/*.tsx` (error.tsx, not-found.tsx, page.tsx).

## Việc cần làm
- Admin (nâng cấp giáo viên, database console, profile, dialog): thay hex/black/white bằng token. Database console: bảng `bg-card`, header `bg-muted`, font mono giữ nguyên.
- `app/error.tsx`, `app/not-found.tsx`: card trung tâm token, thêm gạch `bg-brand-red` trên tiêu đề, nút về trang chủ Button default.
- Các `page.tsx` có class màu cứng → token.

## Giữ nguyên
Heading "Nâng cấp giáo viên", chữ "Đã có lỗi xảy ra", "Không tìm thấy trang".

## Kiểm tra trước khi báo xong
```bash
cd frontend && npm run lint && npm run typecheck
grep -rnE "\[#[0-9a-fA-F]{3,8}\]" <các file trong phạm vi>   # phải rỗng (trừ ngoại lệ PLAN §4)
git diff --stat                                              # chỉ file trong phạm vi
```
Đọc lại `docs/ui-redesign/PLAN.md` §3 (luật cứng) trước khi bắt đầu. Không commit.
