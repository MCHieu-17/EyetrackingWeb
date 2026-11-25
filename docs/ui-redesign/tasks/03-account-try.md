# Task 03 — Trang tài khoản + Try

## Phạm vi
`frontend/components/account/*.tsx`, `frontend/components/try/try-flow.tsx`, `frontend/app/account/**/page.tsx`.

## Việc cần làm
- `auth-layout.tsx`: cột trái thành panel thương hiệu **nền navy** (`bg-primary` hoặc gradient `from-navy-800 to-navy-950`), chữ `text-primary-foreground`/`text-white/75`, logo Fovea; các thẻ tính năng thành card kính mờ (`bg-white/10 border-white/15 backdrop-blur`) — đây là ngoại lệ được dùng `white/…` vì nền luôn navy. Thêm chấm/gạch `bg-brand-red` nhỏ ở eyebrow. Cột phải: `bg-card` form sạch.
- Form login/register/change-password/OTP dialog: thay màu hardcode bằng token; nút "Đăng nhập" chính = Button default (navy). Nút Outlook = outline.
- `try-flow.tsx`: thay toàn bộ hex bằng token theo PLAN §1, giữ bố cục và logic camera. Phần overlay trên video có thể giữ màu cố định (ghi comment).
- Kiểm tra theme tối.

## Giữ nguyên
`#login-email`, `#login-password`, chữ "Đăng nhập", "Đăng ký với Outlook", heading "Chào mừng trở lại", mọi handler.

## Kiểm tra trước khi báo xong
```bash
cd frontend && npm run lint && npm run typecheck
grep -rnE "\[#[0-9a-fA-F]{3,8}\]" <các file trong phạm vi>   # phải rỗng (trừ ngoại lệ PLAN §4)
git diff --stat                                              # chỉ file trong phạm vi
```
Đọc lại `docs/ui-redesign/PLAN.md` §3 (luật cứng) trước khi bắt đầu. Không commit.
