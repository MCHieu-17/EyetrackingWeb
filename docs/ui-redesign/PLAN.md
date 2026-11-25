# Eyetracking UI redesign — design system & luật làm việc

Thương hiệu **Eyetracking**, dự án của Đại học Kinh tế Quốc dân (NEU). Màu nhận diện
(neu.edu.vn): **navy `#084C90`** chủ đạo, **đỏ `#AE152D`** nhấn (dùng tiết chế).
Logo NEU dùng file chính thức từ neu.edu.vn (`frontend/public/brand/neu-logo.webp`).
Font: Source Sans 3 (body, gần Source Sans Pro của NEU), Be Vietnam Pro (tiêu đề).
Có theme sáng + tối (+ theo hệ thống). Trang thu gaze luôn sáng.

Mọi token đã có trong `frontend/app/globals.css` — **không sửa file đó** trừ khi
task ghi rõ.

## 1. Token phải dùng (Tailwind class)

| Mục đích | Class |
|---|---|
| Nền trang | `bg-background` |
| Thẻ/khối nổi | `bg-card text-card-foreground border border-border shadow-sm rounded-2xl` |
| Nền phụ/hover/ô nhập tắt | `bg-muted`, `hover:bg-muted` |
| Chữ chính / phụ | `text-foreground` / `text-muted-foreground` |
| Nút chính, link nổi bật | `bg-primary text-primary-foreground hover:bg-primary-hover` / `text-primary` |
| Nền nhấn nhẹ (chip, tab active, icon box) | `bg-accent text-accent-foreground` |
| Nhấn đỏ NEU (gạch dưới tiêu đề, badge "mới", chấm) | `bg-brand-red`, `text-brand-red`, `bg-brand-red-soft` |
| Viền | `border-border`; ô nhập `border-input` |
| Focus | `focus-visible:ring-2 focus-visible:ring-ring` |
| Trạng thái | `bg-success/10 text-success`, `bg-warning/10 text-warning`, `bg-destructive/10 text-destructive`, `bg-info/10 text-info` |
| Thang màu tĩnh (hiếm dùng) | `bg-navy-50 … bg-navy-950`, `bg-neu-red-50 … 950` |
| Biểu đồ (categorical, thứ tự cố định) | `var(--chart-1)` … `var(--chart-8)`, nền track `bg-chart-track`, lưới `var(--chart-grid)` |
| Heatmap | `rgb(var(--heatmap) / <alpha>)`, legend `from-heatmap-low to-heatmap-high` |
| Bóng | `shadow-xs` / `shadow-sm` / `shadow-md` / `shadow-lg` |
| Tiêu đề | `font-display` (Be Vietnam Pro, đậm, tracking âm) |

### Bảng thay thế màu cũ → token

| Cũ | Mới |
|---|---|
| `bg-white`, `bg-[#fdfdfa]`, `bg-[#fffffb]`, `bg-[#fafbf8]` | `bg-card` (khối) hoặc `bg-background` (nền trang) |
| `bg-[#f5f6f2]`, `bg-[#f7f7f4]`, `bg-[#f2f4ee]`, `bg-[#f0f1ec]`, `bg-[#f0f2ec]` | `bg-muted` (hoặc `bg-background` nếu là nền trang) |
| `border-[#eeeee9]`, `border-[#e8e8e3]`, `border-black/10`, `ring-black/10` | `border-border` / `ring-border` |
| `bg-[#e8f1e6]`, `bg-[#eef3eb]`, `bg-[#dfe9dc]`, `bg-[#e8efe6]` | `bg-accent` |
| `text-[#36533a]`, `text-[#52704f]`, `text-[#3f573c]`, `text-[#52654f]` | `text-accent-foreground` (trên nền accent) hoặc `text-primary` |
| `bg-[#36533a]`, `bg-[#789472]`, `bg-black` (nút/khối nhấn) | `bg-primary text-primary-foreground` |
| `text-black`, `text-[#111111]`, `text-[#2a2a2a]`, `text-[#222320]` | `text-foreground` |
| `text-black/35 … /75`, `text-[#9a9a9a]`, `text-[#777777]` | `text-muted-foreground` |
| `text-white` trên nền primary | `text-primary-foreground` |
| đỏ/nâu lỗi `#7a3b2b #8a3b27 #8b2c25 #7a2e1f #b42318`, nền `#fdf1ec #fdf6f2 #fbf4f2` | `text-destructive`, `bg-destructive/10`, `border-destructive/20` |
| vàng/nâu cảnh báo `#8a6420 #a26a2b #8a6d3b`, nền `#fbf5e7` | `text-warning`, `bg-warning/10` |
| `bg-black/5` | `bg-muted` |
| `border-white/15` (trên nền tối) | `border-border` |

Không còn `#hex` trong `className` (trừ ngoại lệ ở §4). Không dùng `dark:` lẻ tẻ
— token đã tự đổi theo theme; chỉ dùng `dark:` khi token không đủ.

## 2. Phong cách

- Hiện đại, sáng sủa, học thuật: nền `bg-background` xám-xanh rất nhạt; thẻ
  trắng `rounded-2xl` viền mảnh + `shadow-sm`; khoảng trắng rộng.
- Nút: dạng pill (`rounded-full`), nút chính navy. Đỏ NEU chỉ làm điểm nhấn nhỏ
  (thanh `h-1 w-10 rounded-full bg-brand-red` trên tiêu đề trang, chấm trạng
  thái, badge), **không** làm nền khối lớn, không làm nút chính.
- Hover: đổi nền/viền nhẹ, `transition-colors`. Không thêm animation JS; chỉ
  CSS (`animate-fade-in`, `animate-slide-up` đã có) và tôn trọng
  `motion-safe:`.
- Icon: dùng `<Icon name="ri-..."/>` (`components/ui/icon.tsx`). Nếu icon chưa
  có trong map thì thêm import từ `@remixicon/react` vào map đó.
- Mobile 390px không được tràn ngang.

## 3. Luật cứng (vi phạm = task bị trả về)

1. Chỉ sửa file trong phạm vi task. Không sửa `backend/`, `services/`, `db/`,
   `scripts/`, `benchmarks/`, `frontend/e2e/`, `frontend/lib/api/`,
   `frontend/hooks/`, `package.json`, `package-lock.json`.
2. Không cài package. Không đổi logic dữ liệu, query key, hook, props API
   công khai, route, điều kiện hiển thị, handler.
3. Giữ nguyên **chữ hiển thị, aria-label, role, id, htmlFor** (test E2E dựa vào
   chúng): ví dụ "Đăng nhập", "Tạo khóa học", "Xuất bản", "Thêm nội dung",
   "Mở trợ lý học tập", "Nộp bài", "Làm lại", "Giữ kết quả", "Xem lại ca học",
   "Tổng hợp", "Bản đồ nhiệt theo slide", "Lưới heatmap 24x24", `#login-email`,
   `#login-password`, `#new-course-title`… Có thể thêm chữ mới, không đổi chữ cũ.
4. **Vùng AOI — chỉ đổi màu**: các file dưới đây có `data-aoi` mà gaze map
   theo hình học. Chỉ được thay class màu (`bg-*`, `text-*`, `border-<màu>`,
   `ring-<màu>`, `shadow-*`, `fill/stroke`). **Cấm** đổi padding, margin, gap,
   width/height, font-size, line-height, font-weight, rounded, border-width,
   flex/grid, thứ tự/lồng phần tử, và mọi thuộc tính `data-aoi*`:
   - `components/reader/**`
   - `components/student/learning-reader/**`
   - `components/quiz/inline-quiz/**`, `components/quiz/lazy-inline-quiz.tsx`
   - `components/assistant/**`
   - `components/teacher/aoi/student-preview.tsx`
   - `components/teacher/visualization/replay/replay-stage.tsx`
   - `components/calibration/**` (thêm: không đổi vị trí/kích thước điểm hiệu chuẩn)
5. Mảng `COLORS` trong `lib/aoi/colors.ts` phải giữ **đúng 9 phần tử** (màu AOI
   ổn định theo hash).
6. Không commit. Xong phải chạy được:
   `cd frontend && npm run lint && npm run typecheck`.

## 4. Ngoại lệ được giữ hex

- `components/ui/brand-logo.tsx`, `public/brand/*` (màu logo cố định).
- `components/ui/microsoft-logo.tsx` (logo Microsoft).
- `lib/aoi/colors.ts` (màu vùng AOI, đã chọn để phân biệt).
- Overlay trên video/camera/slide cần màu cố định không theo theme (ghi comment).
