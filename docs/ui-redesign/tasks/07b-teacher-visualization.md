# Task 07b — Trực quan hoá (replay + tổng hợp)

## Phạm vi
`frontend/components/teacher/visualization/**`, `frontend/lib/aoi/colors.ts`.
`replay/replay-stage.tsx` thuộc vùng "chỉ đổi màu" (PLAN §3.4).

## Việc cần làm
- Thay ~350 màu hardcode bằng token (PLAN §1). Đây là task lớn: làm tuần tự từng file.
- Biểu đồ (`aoi-bar-chart`, `aoi-composition-chart`, `student-compare-chart`, `visit-trend-chart`):
  - Track/nền thanh: `bg-chart-track` / `var(--chart-track)`; lưới SVG `stroke="var(--chart-grid)"`.
  - Đường/vùng xu hướng: `var(--chart-1)` (đường 2px), vùng `color-mix(in oklab, var(--chart-1) 18%, transparent)`.
  - Chữ nhãn/giá trị dùng `text-muted-foreground`/`text-foreground`, KHÔNG dùng màu series.
- `heatmap-card.tsx`: ô lưới `rgba(180, 83, 9, alpha)` → `rgb(var(--heatmap) / alpha)`; legend gradient `from-heatmap-low to-heatmap-high`. Giữ aria-label "Lưới heatmap 24x24".
- `summary-helpers.ts`: màu "không nhãn" `#a34a32` → `var(--chart-8)`, "khác" `#9ca3af` → `var(--muted-foreground)` (chuỗi CSS var dùng được trong style inline).
- `lib/aoi/colors.ts`: thay 9 màu bằng 8 màu categorical light (#257de0,#f47230,#00b894,#f2a600,#ee7fac,#008a17,#6a4ce2,#ec4647) + `#0e7490`; **giữ đúng 9 phần tử**, giữ hàm `colorFor`.
- Replay sidebar/player/controls/timeline: token; pill trạng thái success/warning/destructive.
- Summary filters/cards/table: token; số liệu lớn `font-display`.

## Giữ nguyên
"Xem lại ca học", "Tổng hợp", heading "Bản đồ nhiệt theo slide", chữ "N lượt xem", "N gaze", "N mẫu trong slide", "Đang tải mẫu gaze...".

## Kiểm tra trước khi báo xong
```bash
cd frontend && npm run lint && npm run typecheck
grep -rnE "\[#[0-9a-fA-F]{3,8}\]" <các file trong phạm vi>   # phải rỗng (trừ ngoại lệ PLAN §4)
git diff --stat                                              # chỉ file trong phạm vi
```
Đọc lại `docs/ui-redesign/PLAN.md` §3 (luật cứng) trước khi bắt đầu. Không commit.
