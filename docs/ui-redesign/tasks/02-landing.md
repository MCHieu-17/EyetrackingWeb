# Task 02 — Landing page

## Phạm vi
`frontend/components/landing/landing-v2.css`, `landing-v2.tsx`, `landing-header.tsx`, `landing-role-tabs.tsx`, `landing-arrow.tsx`.

## Bối cảnh
`landing-v2.css` là CSS scope dưới `.ge-page`, có biến cục bộ (`--ink`, `--brand`, `--pale`...) và ~145 hex xanh rêu cũ (#e8f1e6, #36533a, #789472, #fbfcf9...). Theme tối hiện làm chữ tiêu đề gần như vô hình vì CSS này trộn token mới với hex cũ.

## Việc cần làm
1. Viết lại khối biến đầu `.ge-page` để **mọi** màu tham chiếu token toàn cục: `--ink: var(--foreground)`, `--text: var(--foreground)`, `--muted: var(--muted-foreground)`, `--line: var(--border)`, `--brand: var(--primary)`, `--brand-dark: var(--accent-foreground)`, `--pale: var(--accent)`, `--surface: var(--card)`, `--accent-red: var(--brand-red)`... (đặt tên hợp lý).
2. Thay **toàn bộ** hex trong file CSS bằng các biến đó hoặc `color-mix(in oklab, var(--primary) N%, transparent)` cho gradient/viền mờ. Gradient hero: navy nhạt + chút đỏ NEU rất nhẹ (giống `premium-canvas` trong globals.css). Heatmap minh hoạ có thể dùng `rgb(var(--heatmap) / a)`.
3. Dòng tiêu đề nhấn ("Hiểu cả quá trình học.") dùng `var(--primary)`; thêm chi tiết đỏ NEU nhỏ (gạch/chấm) ở eyebrow.
4. CTA chính: nền `var(--primary)`, chữ `var(--primary-foreground)`. CTA phụ viền.
5. Khối CTA cuối trang: nền navy đậm (`var(--brand-dark)` hoặc `#084c90`→ dùng biến), chữ trắng — tạo điểm nhấn hiện đại.
6. Kiểm tra cả theme tối: mọi chữ đọc được (contrast ≥ 4.5).
7. Mock UI minh hoạ (card, chart) đổi sang tông navy/xám-xanh thay vì xanh rêu.
8. Mobile 390px không tràn ngang; giữ các breakpoint hiện có.

## Giữ nguyên
- Link/nút "Đăng nhập" (e2e dựa vào), cấu trúc section, nội dung chữ (chỉ chữ "GazeEdu" đã đổi thành "Eyetracking").
- `<BrandLogo className="h-8" />`.

## Kiểm tra trước khi báo xong
```bash
cd frontend && npm run lint && npm run typecheck
grep -rnE "\[#[0-9a-fA-F]{3,8}\]" <các file trong phạm vi>   # phải rỗng (trừ ngoại lệ PLAN §4)
git diff --stat                                              # chỉ file trong phạm vi
```
Đọc lại `docs/ui-redesign/PLAN.md` §3 (luật cứng) trước khi bắt đầu. Không commit.
