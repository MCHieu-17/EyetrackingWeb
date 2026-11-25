# Task 06 — Trình soạn nội dung khoá học

## Phạm vi
`frontend/components/teacher/content-editor/**`, `frontend/components/quiz/quiz-question-editor.tsx`.

## Việc cần làm
- Thay toàn bộ hex/black/white bằng token (PLAN §1). ~155 chỗ.
- Outline trái: chương = card `bg-card border-border rounded-2xl`; bài đang chọn `border-primary/40 bg-accent/60`; số thứ tự tròn `bg-accent text-accent-foreground`; icon quiz tròn `bg-primary text-primary-foreground`.
- Vùng kéo-thả upload: `border-dashed border-primary/30 bg-accent/40`, hover đậm hơn.
- Checklist xuất bản: mục đạt `text-success`, chưa đạt `text-warning`/`text-destructive` kèm icon.
- Nút "Xuất bản" = Button default navy.

## Giữ nguyên
"Thêm chương", "Tạo chương đầu tiên", "Thêm nội dung", menuitem "Bài giảng (PDF)", textbox "Tên bài giảng", aria-label "Đổi tên Chương N", "Xuất bản", heading checklist, logic dnd-kit.

## Kiểm tra trước khi báo xong
```bash
cd frontend && npm run lint && npm run typecheck
grep -rnE "\[#[0-9a-fA-F]{3,8}\]" <các file trong phạm vi>   # phải rỗng (trừ ngoại lệ PLAN §4)
git diff --stat                                              # chỉ file trong phạm vi
```
Đọc lại `docs/ui-redesign/PLAN.md` §3 (luật cứng) trước khi bắt đầu. Không commit.
