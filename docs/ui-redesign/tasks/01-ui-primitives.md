# Task 01 — UI primitives (components/ui)

## Phạm vi (chỉ sửa các file này)
`frontend/components/ui/*.tsx` **trừ** `brand-logo.tsx`, `microsoft-logo.tsx`, `icon.tsx`.

## Việc cần làm
- Thay mọi màu hardcode (`bg-[#...]`, `bg-white`, `text-black`, `bg-black`, `text-white`, `border-black/10`...) bằng token theo bảng PLAN §1.
- Button (`button.tsx`): giữ tên variant/size hiện có. Tinh chỉnh: `default` navy (đã đúng token), `outline` = `border-border bg-card hover:bg-muted hover:border-primary/30`, thêm `active:scale-[0.98]` chỉ với `motion-safe:`.
- Input: `bg-card border-input`, focus `focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/25`, placeholder `text-muted-foreground`.
- Badge/Alert: dùng cặp trạng thái `bg-success/10 text-success`... và `bg-accent text-accent-foreground` cho mặc định.
- Dialog/Sheet/Dropdown: nền `bg-popover text-popover-foreground border-border shadow-lg`, overlay `bg-navy-950/40 backdrop-blur-[2px]`.
- Switch: bật = `bg-primary`, tắt = `bg-input`. Progress: track `bg-muted`, thanh `bg-primary`.
- Empty/Error state: icon box `bg-accent text-accent-foreground`, chữ token.
- Phải đẹp ở cả theme sáng và tối (token tự đổi; không thêm `dark:` trừ khi cần).

## Cấm
- Đổi API props/variant names/displayName, đổi cấu trúc Radix, đổi role/aria.

## Kiểm tra trước khi báo xong
```bash
cd frontend && npm run lint && npm run typecheck
grep -rnE "\[#[0-9a-fA-F]{3,8}\]" <các file trong phạm vi>   # phải rỗng (trừ ngoại lệ PLAN §4)
git diff --stat                                              # chỉ file trong phạm vi
```
Đọc lại `docs/ui-redesign/PLAN.md` §3 (luật cứng) trước khi bắt đầu. Không commit.
