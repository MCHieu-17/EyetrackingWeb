# Đánh giá chatbot

Bộ công cụ nhỏ để chạy một tập câu hỏi qua API `POST /chat` của chatbot service,
đo latency và kiểm tra chất lượng citation. Kết quả được ghi ra JSONL để phân
tích tiếp hoặc so sánh giữa các lần chạy.

## File trong thư mục

| File | Mục đích |
|---|---|
| `questions.example.jsonl` | 28 câu hỏi mẫu tiếng Việt, chia nhóm bài giảng, bài tập hint/review, LMS, greeting/thanks và ngoài phạm vi |
| `services/chatbot/scripts/eval_chatbot.py` | Script gửi câu hỏi, đo latency, kiểm tra citation và ghi kết quả |

## Chuẩn bị

1. Chatbot service đang chạy và bạn có `CHATBOT_INTERNAL_TOKEN` khớp với
   service.
2. Thay các placeholder trong `questions.example.jsonl` bằng ID thật:
   - `course_id`, `course_version_id`: khóa học và bản phiên bản cần đánh giá.
   - `thread_id`, `context_key`: phiên chat thật. Câu hỏi LMS gọi backend qua
     `/internal/chat/lms-query` bằng `thread_id` + `context_key`, nên hai giá trị
     này phải thuộc một phiên chat còn hiệu lực.
   - `lesson_id`, `lesson_version_id`: bài giảng tương ứng (nếu muốn chatbot có
     ngữ cảnh bài đang mở).
   - `assignment_id`, `attempt_id`: bài tập và lượt làm bài thật. Nhóm review
     cần `attempt_id` của một lượt **đã nộp** để backend trả đáp án/lời giải.
   - `assignment_context`: đề bài và (với review) bài làm của sinh viên.
3. `httpx` đã có trong `services/chatbot/requirements.txt`; không cần cài thêm
   dependency nào khác.

Các UUID bắt đầu bằng `00000000-0000-0000-0000-0000000000` và chuỗi
`REPLACE_WITH_CONTEXT_KEY` chỉ là placeholder. Nếu chạy nguyên bản mà không
thay, chatbot sẽ không tìm thấy dữ liệu hoặc trả lỗi LMS.

## Cách chạy

Từ repo root:

```bash
export CHATBOT_INTERNAL_TOKEN="token-noi-bo"

python services/chatbot/scripts/eval_chatbot.py \
  --url http://localhost:8002 \
  --input services/chatbot/tests/eval/questions.example.jsonl \
  --output /tmp/chatbot-eval-results.jsonl
```

Hoặc từ `services/chatbot`:

```bash
cd services/chatbot
.venv/bin/python scripts/eval_chatbot.py \
  --input tests/eval/questions.example.jsonl
```

Khi `--input` vẫn là giá trị mặc định, script tự fallback sang
`tests/eval/questions.example.jsonl` tương đối theo vị trí script, nên chạy
được từ cả hai thư mục.

### CLI

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--url` | `http://localhost:8002` | Base URL chatbot; script tự thêm `/chat` nếu chưa có |
| `--token` | env `CHATBOT_INTERNAL_TOKEN` | Token gửi qua header `X-Chatbot-Token` |
| `--input` | `services/chatbot/tests/eval/questions.example.jsonl` | File JSONL câu hỏi |
| `--output` | `/tmp/chatbot-eval-results.jsonl` | File JSONL kết quả (ghi đè mỗi lần chạy) |
| `--timeout` | `120` | Timeout mỗi request, tính bằng giây |

## Format input

Mỗi dòng là một JSON object. Field `question` là bắt buộc và được map sang
`message` của API. Các field còn lại là optional:

| Field | Mặc định | Ghi chú |
|---|---|---|
| `id` | – | Nếu có, được copy nguyên vào output để đối chiếu |
| `question` | – | **Bắt buộc**, map sang `message` |
| `course_id` | `00000000-0000-0000-0000-000000000000` | |
| `course_version_id` | `null` | |
| `thread_id` | `eval-thread` | |
| `context_key` | `""` | |
| `history` | `[]` | List `{role, content}`, role là `student` hoặc `assistant` |
| `lesson_id` | `null` | |
| `lesson_version_id` | `null` | |
| `lesson_title` | `""` | |
| `module_title` | `""` | |
| `attempt_id` | `null` | |
| `assignment_id` | `null` | |
| `assignment_title` | `""` | |
| `assignment_context` | `""` | |
| `support_mode` | `hint` | `hint` hoặc `review` |

Ví dụ:

```json
{"id":"lecture-01","question":"Định nghĩa học máy là gì?","course_id":"...","course_version_id":"...","thread_id":"eval-lecture","lesson_title":"Bài 1: Giới thiệu học máy"}
```

## Format output

Mỗi câu hỏi tạo một dòng JSONL. Record thành công:

```json
{"id":"lecture-01","question":"Định nghĩa học máy là gì?","answer":"...","citations":[{"title":"...","location":"..."}],"intent":"course_qa","verified":true,"finish_reason":"stop","latency_ms":1234.5,"citation_count":3,"citation_valid":true,"citation_ids":[1,3]}
```

| Field | Ý nghĩa |
|---|---|
| `id` | Chỉ có nếu input có `id` |
| `question` | Câu hỏi đã gửi |
| `answer` | Câu trả lời của chatbot |
| `citations` | Danh sách citation nguyên bản từ API |
| `intent` | Intent chatbot phân loại |
| `verified` | Cờ verify của chatbot |
| `finish_reason` | Lý do kết thúc (`stop`, `length`, ...) |
| `latency_ms` | Thời gian request, mili-giây |
| `citation_count` | `len(citations)` |
| `citation_required` | `false` với intent `lms`/`general` (không cần citation slide) |
| `citation_valid` | `true` nếu answer có ít nhất một `[n]` với `1 <= n <= citation_count`; luôn `true` khi `citation_required=false` |
| `citation_ids` | Các số citation tìm thấy trong answer, đã sắp xếp/khử trùng |

Record lỗi HTTP/timeout vẫn được ghi và không dừng cả bộ:

```json
{"id":"lms-01","question":"Deadline nộp bài là khi nào?","error":"HTTP 401: Unauthorized","latency_ms":12.3,"answer":null,"citations":[],"intent":null,"verified":false,"finish_reason":"error","citation_count":0,"citation_valid":false,"citation_ids":[],"status_code":401}
```

`status_code` chỉ có khi lỗi đến từ HTTP response. Timeout/lỗi kết nối không có
field này.

## Đọc kết quả

Cuối mỗi lần chạy, script in summary ra stdout:

```text
=== Tóm tắt đánh giá chatbot ===
Tổng số câu: 28 (lỗi: 1)
Latency câu thành công: p50=1450.2 ms, p95=3820.7 ms
citation_valid: 20/24 (83.3%) trên 24 câu cần citation
verified: 22/28 (78.6%)
finish_reason:
  stop: 24 (85.7%)
  length: 3 (10.7%)
  error: 1 (3.6%)
```

Cách đọc:

- **p50/p95**: chỉ tính trên các câu thành công; câu lỗi/timeout không làm lệch
  phân bố latency.
- **citation_valid**: tỷ lệ trên các câu cần citation (intent khác `lms`/`general`).
  Câu lỗi được tính là không hợp lệ. Một citation chỉ hợp lệ khi số `[n]` nằm
  trong khoảng `1..citation_count`.
- **verified**: tỷ lệ `verified=true` trên toàn bộ câu; câu lỗi tính là `false`.
- **finish_reason**: phân bố lý do kết thúc; câu lỗi nằm trong bucket `error`.
- Muốn xem chi tiết, mở file output và lọc theo `error`, `citation_valid`,
  `verified` hoặc `finish_reason`.

## Lưu ý

- Script gửi **tuần tự** từng câu, không chạy song song. Không nên chạy bộ này
  vào môi trường production đang phục vụ người dùng thật.
- File output bị ghi đè ở mỗi lần chạy; đổi `--output` nếu muốn giữ nhiều bộ kết
  quả.
- Dòng JSON lỗi cú pháp bị bỏ qua kèm cảnh báo ở stderr; dòng thiếu `question`
  vẫn được ghi thành record lỗi để dễ phát hiện.
- Exit code `0` khi đã chạy xong (kể cả có câu lỗi), `2` khi thiếu token, không
  tìm thấy input hoặc input không có câu hợp lệ.
- Có thể tạo file input riêng với ít câu hơn để chạy smoke test nhanh.
