# GazeEdu Frontend

Ung dung Next.js 16 App Router chinh cua GazeEdu, su dung giao dien redesign.

> Mặc định cả stack chạy bằng Docker: `docker compose up -d --build` (xem
> `README.md` gốc). Phần dưới là cách chạy frontend trên host khi cần hot reload.

## Chay local

```bash
npm install
npm run dev
# http://localhost:3000
```

Bien moi truong duoc doc tu **`.env` ở gốc repo** (một file duy nhất cho cả
backend/frontend/chatbot/gaze). Khi chạy `npm run dev` trên host, `next.config.ts`
tự nạp file này; trong Docker, compose truyền build args với tên service.

```env
# URL nội bộ cho rewrite phía server (dev trên host dùng localhost).
API_INTERNAL_URL=http://localhost:8001
GAZE_INTERNAL_URL=http://localhost:8000

# Origin công khai cho browser. Để trống = same-origin qua rewrite.
NEXT_PUBLIC_API_URL=
NEXT_PUBLIC_GAZE_URL=http://localhost:8000
```

## Docker build

```bash
docker compose build frontend
docker compose up -d --build frontend
```

Dockerfile 3 stage: `deps` (`npm ci`) → `builder` (`npm run build`) → `runner`
(Next standalone, chạy `node server.js` bằng user `nextjs`). Các build arg:

| Build arg | Mặc định trong compose | Ý nghĩa |
|---|---|---|
| `API_INTERNAL_URL` | `http://backend:8001` | Rewrite server-side `/api`, `/media` |
| `GAZE_INTERNAL_URL` | `http://gaze:8000` | Rewrite server-side `/gaze` |
| `NEXT_PUBLIC_API_URL` | trống | Origin công khai cho browser (trống = same-origin) |
| `NEXT_PUBLIC_GAZE_URL` | trống | Origin gaze công khai cho browser |

`NEXT_TELEMETRY_DISABLED=1` được đặt trong cả 3 stage để Next không gửi
telemetry khi build/chạy. `NEXT_STANDALONE=1` chỉ bật trong Docker; Vercel
không hỗ trợ `output: standalone`.

## Dynamic imports

Các module nặng được tách chunk bằng `next/dynamic` (`ssr: false`) và chỉ tải
khi thực sự cần:

| Wrapper | Module | Khi nào tải |
|---|---|---|
| `components/pdf/lazy-pdf-page.tsx` | `pdfjs-dist` + PDF page | Khi slide PDF được render |
| `components/teacher/aoi/lazy-aoi-editor.tsx` | AOI editor | Khi mở tab Vùng phân tích |
| `components/quiz/lazy-inline-quiz.tsx` | Quiz runtime | Khi bài học có quiz |
| `components/assistant/lazy-study-assistant-chat.tsx` | Chat + markdown/KaTeX | Khi người dùng mở panel Trợ lý |

Nhờ vậy bundle ban đầu của learning reader không chứa PDF.js, chat markdown
hay editor AOI.

## Lenh

| Lenh | Mo ta |
|---|---|
| `npm run dev` | Chay development server tai port 3000 |
| `npm run build` | Tao production build |
| `npm run start` | Chay production server tai port 3000 |
| `npm run lint` | Kiem tra ESLint |
| `npm run typecheck` | Kiem tra TypeScript |

## Cau truc

```text
app/                    # Routes va layouts
components/
  account/              # Dang nhap
  admin/                # Phan cong va cau hinh calibration
  assistant/            # Widget tro ly hoc tap (chat + citation)
  calibration/          # Calibration dung chung
  layout/               # App shell, topbar (nav + user), sidebar drawer mobile
  quiz/                 # Bài tập trắc nghiệm: soạn, làm bài, chữa bài
  student/              # Dashboard, preflight, learning reader
  teacher/              # Danh sach khoa hoc, workspace, AOI editor
  ui/                   # Radix UI primitives
hooks/                  # TanStack Query, gaze, calibration, AOI snapshot hooks
lib/                    # API client, types, constants, AOI measure utilities
```

## Routes chinh

| Route | Khu vuc |
|---|---|
| `/` | Landing page |
| `/account/login`, `/account/register`, `/account/change-password` | Xác thực |
| `/student` | Trang chu hoc vien |
| `/student/courses/[courseId]` | Learning reader (bài học slide hoặc bài tập trắc nghiệm) |
| `/student/courses/[courseId]/calibrate`, `/prepare` | Hiệu chỉnh gaze / chuẩn bị thiết bị |
| `/student/profile` | Hồ sơ học viên |
| `/teacher` | Danh sach khoa hoc |
| `/teacher/courses/[courseId]` | Course workspace |
| `/teacher/profile` | Hồ sơ giáo viên |
| `/admin`, `/admin/profile` | Quan tri, phan cong |
| `/try` | Trai nghiem khach |

## Trợ lý học tập

- Nút **Trợ lý** trên header reader mở panel **dock bên phải** (kiểu Copilot),
  dùng chung cho cả bài giảng và bài tập. Chỉ hiện ở desktop `xl` (>=1280px);
  mobile không thiết kế chat.
- Panel rộng `clamp(240px, 18vw, 400px)`, cao hết vùng nội dung. Outline thu còn
  `220px`; slide tự co theo phần còn lại (trên màn 1920px slide vẫn giữ max
  1120px, chỉ dịch trái).
- Trước khi nộp chỉ gợi ý, sau khi nộp mới chữa bài. Mode được chia sẻ qua
  `components/assistant/assistant-context.tsx`; `InlineQuiz` đăng ký
  `assignmentId` + mode quiz/review, reader root chỉ render một panel chat.
- SSE: `status → citations → token → done`; answer chỉ stream sau khi verify citation.
- Citation chip mở modal trang PDF (PDF.js) + snippet.
- API client: `lib/api/chat.ts`; hooks: `hooks/use-chat.ts`; UI:
  `components/assistant/study-assistant-chat.tsx`.

Nhung URL cu `/student/my-courses`, `/teacher/courses` va `/admin/courses`
duoc redirect sang route moi tuong ung.

## Bài tập trắc nghiệm

Bài tập là một **item trong chương**, cùng cấp với bài học slide:

- Dữ liệu: `lessons.kind` = `lesson` (slide) hoặc `quiz`; item `quiz` có đúng một
  `quiz_specs` (1:1) chứa câu hỏi, thời lượng, hạn nộp (tùy chọn).
- Giáo viên soạn ngay trong workspace khóa học (tab **Nội dung**) qua nút
  "Thêm trắc nghiệm"; câu hỏi hỗ trợ một hoặc nhiều đáp án đúng (chấm tất cả-hoặc-không).
- Học viên gặp bài tập như một bước trong learning reader; làm bài, được chấm và có
  nút "Bài tiếp theo" ngay trong luồng học. Bài tập **cũng ghi dữ liệu gaze** (toạ độ
  theo viewport, `content_presentations.surface = 'quiz'`, không có slide).
  Gaze RAW theo viewport được ghi vào `gaze_samples` cho phân tích AOI.
- **Làm lại**: giáo viên bật công tắc **Cho phép học viên làm lại** ngay đầu phần
  soạn bài tập (bật là lưu ngay, không cần bấm Lưu); học viên thấy nút **Làm lại** ở
  trang kết quả → xoá lượt làm cũ, đồng hồ chạy lại, đáp án ẩn lại cho tới khi nộp
  lần mới (mỗi học viên vẫn chỉ giữ 1 lượt).

## Workspace soạn nội dung của giáo viên

`/teacher/courses/{courseId}` có **5 tab** (`?tab=`, xem
`components/teacher/course-workspace.tsx`):

| Tab | Nội dung |
|---|---|
| **Nội dung** | Soạn chương/bài giảng/bài tập (mặc định) |
| **Thông tin khóa học** | Tên, mô tả, xuất bản / thu hồi / lưu trữ, xoá khóa học |
| **Cài đặt** | Thiết lập ít dùng áp cho cả khóa (hiển thị điểm nhìn, bắt buộc hiệu chỉnh) |
| **Học viên** | Ghi danh, danh sách, drawer chi tiết từng học viên |
| **Vùng phân tích** | Editor 2 khung: khung học viên + định nghĩa vùng; tự lưu & áp dụng |

### AOI editor (`?tab=aoi`)

- **Khung trái** dùng chung `ReaderFrame` với trang học viên (header, mục lục,
  slide PDF, nav, trợ lý) nên giáo viên thấy đúng giao diện thật.
- **Khung phải** chọn bài/trang, chuyển tab **Slide** / **Giao diện**, đổi tên,
  ẩn/hiện hoặc xóa vùng.
- **Chế độ Chỉnh vùng**: bấm vào một phần để chọn; kéo trên slide để vẽ vùng nội
  dung; kéo trên trang để vẽ vùng giao diện tự do (neo vào thành phần ổn định
  gần nhất + tọa độ tương đối).
- **Chế độ Tương tác**: khung trái hoạt động như học viên (đổi bài, chuyển
  trang, mở chat, làm quiz); quay lại Chỉnh vùng giữ nguyên trạng thái.
- Mỗi slide có bộ vùng riêng: `slide_n` (container) + gợi ý PyMuPDF (`TEXT`,
  `IMAGE`, `TABLE`; mỗi block là một vùng) + vùng tự vẽ. Bộ vùng giao diện
  dùng chung toàn hệ thống.
- **Tạo lại gợi ý**: thay các vùng gợi ý tự động bằng kết quả PyMuPDF mới.
  Có 2 lựa chọn: chỉ thay vùng gợi ý (giữ vùng tự vẽ) hoặc đặt lại toàn bộ
  (xoá cả vùng tự vẽ, chỉ giữ container `slide_n`).
- Mọi bộ vùng có `no_label`; vùng không được đánh dấu tự động gom vào
  “Chưa đánh dấu”.
- **Bỏ đánh dấu** một vùng slide sẽ giữ vùng đó trong danh sách (mờ đi, nhãn
  “Chưa đánh dấu”) thay vì xóa hẳn; giáo viên có thể bật lại bất kỳ lúc nào.
  Vùng đã bỏ đánh dấu không tham gia phân tích, gaze trong vùng đó được tính là
  `no_label`.
- Thay đổi được **tự lưu + tự áp dụng**; không có nút publish kỹ thuật.
- Runtime (`useAoiSnapshot`) đo `getBoundingClientRect()` của mọi `[data-aoi]`
  và gửi layout snapshot mỗi khi layout đổi (mở/đóng chatbot, mục lục, đổi
  slide, tin nhắn mới, scroll/resize). `layoutKey` là `reader` / `reader-chat` /
  `quiz` / `quiz-chat`.
- `data-aoi` hiện có: `reader-root`, `header`, `outline`, `lesson-content`,
  `slide`, `lesson-nav`, `quiz`, `quiz-question`, `quiz-options`,
  `quiz-submit`, `chatbot`, `chat-header`, `chat-messages`,
  `chat-user-message`, `chat-ai-message`, `chat-input`, `chat-send`,
  `chat-open-button`.
- **Viewport thích nghi với zoom/resize**: `useGazeTracker` quy đổi toạ độ gaze
  từ hình chữ nhật vật lý của viewport lúc calibration (`screenX/Y`,
  `innerWidth/Height`, DPR) sang viewport hiện tại. Zoom, resize và move cửa sổ
  không cần hiệu chỉnh lại; `useAoiSnapshot` vẫn tạo layout snapshot mới khi
  viewport đổi.

Tab **Nội dung** là **master–detail**: mục lục bên trái (`content-outline.tsx` — chương,
bài giảng, bài tập, badge trạng thái thiếu/đủ nội dung, dòng đang chọn có viền đậm) và
trình soạn bên phải (`item-editor.tsx` → `lesson-editor.tsx` hoặc
`lesson-quiz-editor.tsx`). Không còn accordion lồng nhau; màn hình nhỏ thì mục lục thu
gọn sau nút **Mục lục** nhưng thanh trên vẫn hiện tên mục đang sửa.

- Thêm mục: nút có chữ **Thêm bài giảng** / **Thêm trắc nghiệm** trong từng chương; mục
  mới được tạo ở dạng nháp rồi **mở ngay** để giáo viên nhập tiếp.
- Bấm trực tiếp vào tên chương/bài giảng/bài tập trong mục lục để đổi tên tại chỗ
  (Enter để lưu, Esc để huỷ). Nút thùng rác bên cạnh mỗi mục dùng để xoá.
- Tên bài giảng cũng sửa được ở tiêu đề trình soạn (lưu khi rời ô / Enter); tên bài
  tập sửa ở ô **Tên bài tập** trong phần soạn câu hỏi.

### Lưu và xuất bản

| Thao tác | Lưu khi nào |
|---|---|
| Tên/mô tả khóa học, trạng thái | bấm **Lưu thay đổi** / **Xuất bản khóa học** (tab Thông tin khóa học) |
| Công tắc điểm nhìn (cấp khóa) | bấm là lưu ngay |
| Tên chương | Enter/rời ô trong menu **Đổi tên chương** |
| Tên bài giảng | Enter/rời ô ở tiêu đề trình soạn |
| Tải tài liệu | chọn PDF/PPTX/PPT/ODP là tải ngay; **bài đã có slide phải xác nhận** (thay tài liệu xoá toàn bộ slide cũ, và bị từ chối nếu bài đã có dữ liệu điểm nhìn) |
| Bài tập trắc nghiệm (câu hỏi, thời lượng, hạn, hướng dẫn) | **Lưu bài tập nháp** / **Giao bài cho học viên** |
| Cho phép làm lại | bấm là lưu ngay |

- **Lưu nháp không bắt câu hỏi hoàn thiện**: câu còn dở vẫn nằm trên màn hình và được
  đánh dấu, nhưng do schema `PATCH /api/assignments/{id}` từ chối lựa chọn rỗng nên
  **chỉ những câu hợp lệ được gửi lên** (thông báo ghi rõ "N câu chưa hoàn thiện…").
  Chỉ **Giao bài cho học viên** mới bắt buộc mọi câu hợp lệ.
- **Giao bài cho học viên** xuất bản course version nháp hiện tại (kéo theo các
  thay đổi nháp khác của khóa học) để sinh viên thấy bài tập. Bài tập đã có trong
  bản xuất bản được coi là “Đã giao” kể cả khi giáo viên đang sửa một lesson
  version nháp mới; khi có thay đổi chưa xuất bản, nút đổi thành **Cập nhật cho
  học viên**.
- Ràng buộc câu hỏi tập trung ở `lib/quiz-validation.ts` (khớp `schemas/quiz.py`), dùng
  chung cho việc báo lỗi tại chỗ và luồng lưu nháp.
- Trước khi xuất bản, **Kiểm tra nội dung** (tab Nội dung) hoặc danh sách ngay trong tab
  Thông tin khóa học liệt kê mục còn thiếu. Vấn đề **bắt buộc** khớp backend
  (`content.validate_draft`): cần tên khóa học, có chương, có ít nhất một mục, bài giảng
  phải có slide và **toàn bộ slide đã index xong cho trợ lý học tập**, bài tập phải có
  câu hỏi. Bài tập còn nháp chỉ là cảnh báo vì xuất bản khóa học sẽ đưa nó vào bản
  published. Slide lỗi/đang chờ có nút **Thử lại index** trong trình soạn bài giảng;
  hệ thống tự index nền ngay sau khi tải tài liệu lên.
- Đổi mục/tab/rời trang khi còn dữ liệu chưa lưu → hộp thoại
  **Còn thay đổi chưa lưu** (Ở lại / Bỏ thay đổi / Lưu & tiếp tục), xem
  `components/teacher/unsaved-guard.tsx`.

## Sắp xếp nội dung chương (kéo thả)

Trong tab **Nội dung**, mỗi dòng bài học/bài tập có **tay kéo** ở đầu dòng
(`components/teacher/content-editor/sortable-row.tsx`, dùng `@dnd-kit`):

- Kéo thả đổi thứ tự item **trong cùng một chương**; bài học và bài tập dùng chung
  `lessons.order_index` nên trộn lẫn nhau được.
- Thao tác bằng bàn phím: nhấn `Space` để nhặt, `↑`/`↓` để di chuyển, `Space` để thả,
  `Esc` để huỷ (có thông báo qua `aria-live`).
- Thứ tự được cập nhật lạc quan (hiện ngay), rồi gửi
  `POST /teacher/modules/{id}/items/reorder` với **toàn bộ** danh sách item của chương;
  lỗi thì khôi phục thứ tự cũ và báo đỏ.
