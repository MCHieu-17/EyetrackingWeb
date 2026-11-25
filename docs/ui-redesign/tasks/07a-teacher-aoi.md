# Task 07a — Trình vẽ vùng AOI của giáo viên

## Phạm vi
`frontend/components/teacher/aoi/**` **trừ** `student-preview.tsx` (chỉ được đổi màu ở file đó, xem PLAN §3.4), `frontend/components/teacher/aoi-editor.tsx`.

## Việc cần làm
- Thay hex/black/white bằng token. Màu từng vùng AOI vẫn lấy từ `colorFor()` (`lib/aoi/colors.ts`) — không đổi.
- Panel danh sách AOI: hàng hover `hover:bg-muted`, chọn `bg-accent`; nút chế độ "Chỉnh vùng"/"Tương tác" thành segmented control (active `bg-primary text-primary-foreground`).
- Trong `student-preview.tsx`: CHỈ đổi class màu của thanh công cụ phía trên khung preview; không đụng khung `ReaderFrame`, kích thước, scale.

## Kiểm tra trước khi báo xong
```bash
cd frontend && npm run lint && npm run typecheck
grep -rnE "\[#[0-9a-fA-F]{3,8}\]" <các file trong phạm vi>   # phải rỗng (trừ ngoại lệ PLAN §4)
git diff --stat                                              # chỉ file trong phạm vi
```
Đọc lại `docs/ui-redesign/PLAN.md` §3 (luật cứng) trước khi bắt đầu. Không commit.
