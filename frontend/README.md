# Frontend — GazeEdu / EyeLearning

Next.js 16 App Router, React 19, TypeScript, Tailwind 4, TanStack Query.
Yêu cầu Node **>=20.19**; Docker image dùng Node 22 LTS.

## Chạy

Stack mặc định chạy Docker từ root repo:

```bash
docker compose up -d --build
```

Hot reload trên host:

```bash
cd frontend
npm install
npm run dev
# http://localhost:3000
```

Frontend đọc `.env` ở gốc repo. Khi chạy host:

```env
API_INTERNAL_URL=http://localhost:8001
GAZE_INTERNAL_URL=http://localhost:8000
NEXT_PUBLIC_API_URL=
NEXT_PUBLIC_GAZE_URL=http://localhost:8000
```

Để trống `NEXT_PUBLIC_*` nghĩa là browser dùng same-origin qua nginx/Next
rewrite.

## Lệnh

| Lệnh | Mục đích |
|---|---|
| `npm run dev` | Dev server cổng 3000 |
| `npm run build` | Production build |
| `npm run lint` | ESLint |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run test` | Vitest |
| `npm run knip` | File/export/dependency thừa |
| `npm run test:e2e` | Playwright (stack phải chạy) |

## Cấu trúc

```text
app/                    # Route/layout; page chỉ composition
components/
├── account/            # đăng nhập, đổi mật khẩu
├── admin/              # quản trị user + database console
├── assistant/          # chat panel, citation, markdown
├── calibration/        # UI calibration dùng chung
├── layout/             # app shell/sidebar/topbar
├── pdf/                # lazy PDF.js page
├── quiz/               # làm/chữa/soạn quiz
├── reader/             # khung reader dùng chung giáo viên/học viên
├── student/            # preflight, learning reader
├── teacher/             # course workspace, content editor, AOI
├── try/                # trang trải nghiệm
└── ui/                 # primitives
hooks/                  # hook dùng chung nhiều feature
lib/
├── api/                # transport + request/response mapping
├── aoi/                # geometry/measure/color helpers
├── types/              # domain types dùng chung
├── query-keys.ts       # nguồn query key duy nhất
├── gaze-queue.ts       # IndexedDB queue
└── gaze-sender.ts      # flush/retry idempotent
```

Quy ước:

- Route không chứa business logic lớn.
- Component không tự gọi `fetch` nếu đã có `lib/api` + hook TanStack Query.
- Hook chỉ dùng một feature đặt cạnh feature; `hooks/` chỉ chứa hook dùng chung.
- Query key lấy từ `lib/query-keys.ts`.
- Pure helper có test đặt cạnh helper.

## Routes chính

| Route | Khu vực |
|---|---|
| `/` | Landing |
| `/account/login`, `/account/register`, `/account/change-password` | Auth; đăng nhập/tạo tài khoản bằng Outlook + OTP |
| `/student` | Dashboard học viên |
| `/student/courses/[courseId]` | Learning reader slide/quiz |
| `/student/courses/[courseId]/calibrate`, `/prepare` | Calibration/preflight |
| `/student/profile` | Hồ sơ |
| `/teacher` | Danh sách khóa |
| `/teacher/courses/[courseId]` | Workspace giáo viên 5 tab |
| `/teacher/profile`, `/admin`, `/admin/profile` | Giáo viên/admin |
| `/admin/database` | Truy vấn DB read-only |
| `/try` | Trải nghiệm khách |

## Gaze flow phía client

1. `useGazeTracker` xin webcam, gửi frame ~12 FPS qua WebSocket `/gaze`.
2. Frame protocol v2 gồm header JSON + JPEG; metadata có presentation/layout.
3. `ReaderContent` tạo `content_view` theo slide/quiz.
4. `useAoiSnapshot` đo DOM, tạo `view_layout` khi layout đổi.
5. Gaze point gom batch 1,5 giây hoặc 40 sample; gửi backend.
6. Batch được persist IndexedDB trước khi POST; retry giữ nguyên
   `batchId`/payload để backend dedup.
7. `useDisplayGuard` chặn/không ghi gaze khi phát hiện zoom trình duyệt hoặc
   fullscreen ở trang calibration/reader.
8. Resize cửa sổ tạm dừng ghi gaze ngay; `useAoiSnapshot` tạo layout mới rồi
   mới ghi tiếp. Gaze được quy đổi từ viewport lúc calibration sang viewport
   hiện tại khi resize/move cửa sổ.

Bất biến:

- Toạ độ gaze chuẩn hóa `[0,1]` theo viewport hiện tại; layout cũng ở cùng
  hệ toạ độ. Không còn `original-v1`/`visible_rect`.
- Không ghi sample khi presentation/layout chưa sẵn sàng.
- Không ghi sample khi display guard đang chặn.
- Đổi slide/layout phải flush batch cũ trước.
- Cleanup phải đóng WebSocket, camera và timer.
- UI không hardcode pixel cho tọa độ gaze.

## Learning reader và quiz

- Slide PDF render bằng PDF.js theo `page_number`.
- Quiz config nằm trong `lessons.quiz_config`; API dùng `lessonId` hiện hành.
- Làm lại quiz giữ lịch sử attempt; attempt `submitted` dùng `quiz_snapshot`.
- Chat panel nhận attempt/assignment context; chế độ `hint` trước nộp,
  `review` sau nộp.

## Teacher workspace

`/teacher/courses/{id}?tab=...`:

| Tab | Nội dung |
|---|---|
| Nội dung | chương/bài/quiz, upload slide, thứ tự item |
| Thông tin | tên/mô tả/publish/archive/delete |
| Cài đặt | gaze dot, bắt buộc calibration |
| Học viên | ghi danh, tiến độ |
| Vùng phân tích | AOI slide/UI, autosave |

Slide upload chỉ trả job ID; UI poll trạng thái import/index. Replace tài liệu
xoá slide cũ và cascade gaze/AOI tương ứng.

AOI editor:

- dùng chung `ReaderFrame` với học viên;
- khung reader cố định: slide co vừa vùng nội dung, không cuộn dọc; nút
  Trước/Sau là footer ngoài slide;
- quiz không cuộn toàn khung; chỉ danh sách đáp án/review cuộn nội bộ khi dài;
- slide AOI lưu trong `aois`, UI schema `reader-v1`;
- giáo viên tự đặt nhãn slide dạng `AOI_THANHCHAT`, `AOI_BANGBIEU`… (regex
  `^AOI_[A-Z0-9_]{1,60}$`, unique trong slide); nhãn mặc định là `AOI_n`;
- UI dùng tên vùng (ví dụ “Mục lục”, “Thanh chat”);
- worker gắn một nhãn duy nhất: `SLIDE_<label>` / `SLIDE_NO_LABEL` hoặc tên UI /
  `UI_NO_LABEL`;
- không còn nút “Tạo lại gợi ý” hay sinh vùng từ PDF;
- nút thùng rác xóa hẳn vùng; “Bỏ đánh dấu” giữ vùng để bật lại;
- thay đổi tự lưu; đổi slide phải flush/không gửi nhầm context;
- không có publish AOI riêng.

## Chatbot

- SSE `status → citations → token → done`.
- Citation map sang slide/PDF trong reader.
- Backend là nguồn lịch sử chat; frontend không giữ checkpointer.
- Markdown/math/citation nặng được lazy-load cùng panel chat.

## Kiểm tra trước merge

```bash
npm run lint
npm run typecheck
npm run knip
npm run test
npm run build
```

E2E cần stack đang chạy:

```bash
./scripts/e2e.sh
```
