# Chatbot service (RAG hỗ trợ học tập)

FastAPI + LLM/VLM qua endpoint OpenAI-compatible: ingest slide bằng VLM →
hybrid retrieval (Postgres FTS + pgvector + HyDE) → một LLM call streaming →
kiểm tra citation bằng code → SSE.

Chatbot chạy **CPU-only**: embedding local `Qwen3-Embedding-0.6B` trên CPU,
LLM/VLM gọi endpoint OpenAI-compatible (ví dụ Qwen 3.5 35B). Không cần GPU và
không đặt `gpus: all` — GPU chỉ dành cho `services/gaze`.

## Endpoints

| Method | Path | Auth | Mục đích |
|---|---|---|---|
| GET | `/health` | – | Liveness, luôn 200 |
| GET | `/ready` | – | Readiness, 503 khi DB không truy cập được |
| POST | `/chat` | `X-Chatbot-Token` | Hỏi đáp non-streaming |
| POST | `/chat/stream` | `X-Chatbot-Token` | SSE: status → citations → token → done |
| POST | `/ingest/slides` | `X-Chatbot-Token` | Embed danh sách slide ID |
| POST | `/ingest/reindex-all` | `X-Chatbot-Token` | Backfill slide chưa ready |

## Luồng xử lý

```
POST /chat/stream
  ├─ greeting/thanks fast path (không retrieval)
  ├─ LMS detection (regex) → pure LMS: backend query + render Markdown
  ├─ query prep (0–1 LLM call nhỏ)
  │    ├─ rewrite theo history (nếu có đại từ/ngữ cảnh)
  │    └─ HyDE (nếu câu ngắn/mơ hồ)
  ├─ retrieval
  │    ├─ BM25-like: Postgres FTS ts_rank_cd
  │    ├─ dense: pgvector với query đã rewrite
  │    └─ dense: pgvector với HyDE text (nếu có)
  │         └─ RRF fusion → top-k docs
  ├─ generation: một LLM call streaming
  └─ citation: hậu kiểm + chèn "Nguồn tham khảo" nếu model không cite
```

- **Không còn router LLM, verifier LLM, NDJSON block hay LangGraph.** Mỗi
  request tối đa 2 LLM call (1 query prep nhỏ + 1 answer streaming), không retry
  toàn bộ câu trả lời.
- **Một chatbot duy nhất** cho bài giảng và bài tập. Không còn prompt/verifier
  riêng cho exercise.
- **Citation**: mỗi claim về môn học phải có `[n]`. Code hậu kiểm `[n]` nằm
  trong khoảng hợp lệ; nếu model không cite, pipeline chèn "Nguồn tham khảo" và
  đặt `finish_reason="citation_fallback"` để vẫn có nguồn.
- **Bài tập chưa nộp**: prompt-level không lộ đáp án/lời giải; chỉ gợi ý phương
  pháp và câu hỏi dẫn dắt. Không còn leakage verifier.
- **Bài tập đã nộp**: được giải thích đáp án đúng/lỗi sai từ ngữ cảnh bài tập
  của backend.
- **Kiến thức ngoài tài liệu**: phải nằm dưới label `Ngoài tài liệu môn học:`
  và không gắn citation.
- **LMS**: deadline/điểm/cấu trúc khóa được nhận diện bằng regex, gọi
  `/internal/chat/lms-query`; câu hỏi thuần LMS được render trực tiếp, câu hỏi
  mixed được inject context vào prompt.
- **Streaming**: token được phát ngay khi LLM trả về; citation được kiểm tra
  sau khi stream xong, không buffer và không retry.
- **HyDE trên CPU**: embedding local chạy CPU nên HyDE text càng dài càng tốn
  thời gian. Pipeline chỉ dùng HyDE cho câu ngắn/mơ hồ, không dùng cho follow-up
  (rewrite xử lý) và câu đã có chủ thể cụ thể. Nếu ưu tiên latency tuyệt đối, đặt
  `HYDE_ENABLED=false`; retrieval vẫn chạy BM25 + dense query gốc. Kết quả
  rewrite/HyDE được cache TTL 300 s theo câu hỏi + hash history.
- **Embedding**: một instance model dùng chung cho query và ingest, với hai lane
  worker riêng để query không xếp sau batch ingest.

## Cấu hình (biến môi trường)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `CHATBOT_DATABASE_URL` | – | DSN psycopg (`postgresql://...`), không dùng `+asyncpg` |
| `CHATBOT_DB_POOL_MIN/MAX` | `1/10` | Pool PostgreSQL riêng của chatbot |
| `CHATBOT_DB_POOL_TIMEOUT` | `10` | Chờ connection tối đa (giây) |
| `CHATBOT_DB_POOL_RECONNECT_TIMEOUT` | `10` | Chu kỳ reconnect (giây) |
| `CHATBOT_INTERNAL_TOKEN` | – | Token nội bộ (bắt buộc) |
| `EMBEDDING_NAME` | **bắt buộc** | `local` (hiện là backend duy nhất) |
| `EMBEDDING_DIM` | **bắt buộc** | Phải khớp `vector(1024)` trong `001_baseline.sql` |
| `EMBEDDING_MODEL_PATH` | **bắt buộc** | Đường dẫn weights, ví dụ `/app/weights/Qwen3-Embedding-0.6B` |
| `EMBEDDING_DEVICE` | **bắt buộc** | `cpu` \| `cuda` (cuda chỉ khi tự build image GPU) |
| `EMBEDDING_LOCAL_FILES_ONLY` | **bắt buộc** | `true` \| `false` |
| `EMBEDDING_HF_REPO` | **bắt buộc** | Repo HuggingFace, ví dụ `Qwen/Qwen3-Embedding-0.6B` |
| `LLM_BASE_URL` | – | Endpoint Chat Completions OpenAI-compatible (bắt buộc) |
| `LLM_API_KEY` | – | API key của endpoint (bắt buộc nếu dùng auth header) |
| `LLM_AUTH_HEADER` | `Authorization` | Tên header auth; để trống nếu endpoint không cần auth |
| `LLM_AUTH_SCHEME` | `Bearer` | Scheme auth; để trống nếu header nhận raw key |
| `LLM_MODEL` | – | Model chat cho query prep/answer (bắt buộc) |
| `VLM_MODEL` | = `LLM_MODEL` | Model vision cho ingest slide |
| `LLM_ENABLE_THINKING` | `false` | Bật reasoning nếu endpoint hỗ trợ (không khuyến nghị) |
| `LLM_TIMEOUT` | `180` | Timeout mặc định cho LLM call |
| `LLM_MAX_RETRIES` | `2` | Retry cho VLM ChatOpenAI |
| `ANSWER_MAX_TOKENS` | `2048` | Max output cho answer |
| `ANSWER_TEMPERATURE` | `0.2` | Nhiệt độ sinh answer |
| `LLM_QUERY_MAX_TOKENS` | `400` | Max output cho query rewrite/HyDE |
| `LLM_QUERY_TIMEOUT` | `3` | Timeout cho query prep (fallback câu gốc) |
| `LLM_ANSWER_TIMEOUT` | `120` | Timeout cho answer streaming |
| `LLM_QUEUE_TIMEOUT` | `5` | Chờ slot generation/total trước khi bỏ |
| `LLM_GENERATION_CONCURRENCY` | `6` | Slot gọi LLM generation đồng thời |
| `LLM_TOTAL_CONCURRENCY` | `6` | Slot LLM tổng (query + answer) |
| `CHATBOT_MAX_CONCURRENT` | `6` | Slot chat đồng thời; vượt → 429 sớm |
| `VLM_MAX_TOKENS` | `8192` | Max output cho VLM |
| `VLM_TIMEOUT` | `300` | Timeout cho VLM ingest |
| `VLM_INGEST_CONCURRENCY` | `4` | Slot VLM + số thread render/VLM mỗi request |
| `VLM_INGEST_QUEUE_TIMEOUT` | `900` | Chờ slot VLM tối đa (giây) |
| `EMBEDDING_NUM_THREADS` | `4` | Torch intra-op, khớp CPU quota container |
| `RAG_TOP_K` | `8` | Số slide trả về sau RRF |
| `RAG_BM25_CANDIDATES` | `20` | Candidate nhánh BM25-like |
| `RAG_DENSE_CANDIDATES` | `20` | Candidate nhánh dense |
| `RAG_HYDE_CANDIDATES` | `20` | Candidate nhánh HyDE |
| `RAG_HYDE_WEIGHT` | `0.7` | Trọng số RRF cho nhánh HyDE |
| `RAG_RRF_K` | `60` | Hằng số RRF |
| `RAG_SCORE_THRESHOLD` | `0.2` | Ngưỡng cosine tối thiểu |
| `QUERY_REWRITE_ENABLED` | `true` | Bật rewrite theo history |
| `HYDE_ENABLED` | `true` | Bật HyDE |
| `HYDE_MIN_QUERY_WORDS` | `8` | Câu ngắn hơn + mơ hồ/không có chủ thể → HyDE |
| `CITATION_GATE_TOKENS` | `200` | Deprecated, không còn được pipeline đọc |
| `CITATION_RETRY_MAX` | `1` | Deprecated, không còn retry câu trả lời |
| `LMS_DETECTION_ENABLED` | `true` | Bật regex LMS |
| `LOCAL_MEDIA_DIR` | `/app/media` | Thư mục slide local |
| `STORAGE_HTTP_ALLOWED_HOSTS` | – | Host HTTP được phép fetch slide |
| `R2_*` | – | Cloudflare R2 (nếu dùng) |

`app/settings.py` cung cấp `validate()` để fail-fast lúc khởi động nếu cấu hình
thiếu/sai.

## DB role hạn chế

Chatbot dùng role `chatbot_reader` (xem `CHATBOT_DB_USER`/`CHATBOT_DB_PASSWORD`):
- được `SELECT` các view outline;
- được `SELECT` và `UPDATE` các cột index trên `slides`
  (`transcript`, `embedding`, `index_status`, `index_error`,
  `pipeline_version`, `model_version`);
- **không** có quyền đọc `quiz_attempts`, `users`, `chat_*`.

Role được service `migrate` tự tạo/cập nhật sau mỗi lần áp migrations (đọc
`CHATBOT_DB_USER`/`CHATBOT_DB_PASSWORD`). Khi muốn cấp lại quyền ngay, chạy lại
migration (idempotent):

```bash
docker compose run --rm migrate
```

`GET /ready` trả `503` kèm `detail` nếu không kết nối được DB (sai role/password,
DB chưa lên). Các endpoint `/ingest/*` trả `503` kèm lý do thật thay vì `500`;
backend lưu lý do vào `slides.index_error`.

Đây là lớp bảo vệ thứ hai: kể cả khi prompt injection yêu cầu lộ đáp án, chatbot
cũng không đọc được bảng quiz.

## Chạy local (không Docker)

```bash
cd services/chatbot
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-embedding.txt
EMBEDDING_MODEL_PATH="$PWD/weights/Qwen3-Embedding-0.6B" \
EMBEDDING_DEVICE=cpu \
CHATBOT_DATABASE_URL="postgresql://postgres:...@localhost:5435/eyetracking" \
  .venv/bin/python -m uvicorn app.main:app --port 8002
```

Lần đầu cần tải weights:

```bash
EMBEDDING_MODEL_PATH="$PWD/weights/Qwen3-Embedding-0.6B" \
  .venv/bin/python -m scripts.download_embedding
```

## Docker và GPU

- `services/chatbot/Dockerfile` là multi-stage: stage `ai-base` cài
  torch/torchvision CPU, stage `runtime` cài deps chatbot.
- Compose **không** đặt `gpus: all` cho chatbot; đặt `EMBEDDING_DEVICE=cpu`
  tường minh trong `.env`/`stack.env` (không có default trong code).
- Build: `docker compose build chatbot` hoặc `docker compose up -d --build`.
- Không khuyến nghị đẩy embedding lên GPU: sửa stage `ai-base` trong
  `services/chatbot/Dockerfile` sang wheel CUDA, đặt `EMBEDDING_DEVICE=cuda`
  và thêm `gpus: all` — chỉ làm khi gaze không cần GPU.

## Kiến trúc mã

```
app/
├── main.py                 FastAPI, lifespan (pool + warm-up embedding), /health, /ready
├── settings.py             đọc & validate biến môi trường
├── db.py                   ConnectionPool dùng chung (pgvector register)
├── schemas.py              request/response
├── api/
│   ├── chat.py             /chat, /chat/stream (SSE)
│   └── ingest.py           /ingest/*
├── services/
│   ├── ingest.py           slide -> VLM -> embedding -> pgvector
│   └── storage.py          đọc file từ local/S3/R2/URL (chống SSRF)
└── workflow/
    ├── query.py            rewrite + adaptive HyDE
    ├── retrieval.py        BM25-like + dense + HyDE + RRF
    ├── generation.py       prompt + stream answer
    ├── citations.py        parse/validate citation
    ├── lms.py              LMS detection + backend query + render
    ├── pipeline.py         orchestration tuyến tính + SSE events
    ├── prompts.py          prompt query/answer/VLM
    ├── history.py          chuẩn hoá lịch sử
    ├── llm.py              AsyncOpenAI transport + concurrency
    ├── providers.py        embedding/VLM factories
    ├── embedding_queue.py  hai lane query/ingest dùng chung một model
    └── workload.py         ingest nhường ưu tiên cho chat
```

## Runtime và rollout

- Không dùng checkpointer; backend là nguồn sự thật cho lịch sử.
- `pipeline.py` là async generator tự viết, không phải LangGraph.
- LLM/VLM dùng chung AsyncOpenAI transport, giới hạn generation/total
  concurrency và request pacing. Cấu hình `LLM_GENERATION_CONCURRENCY` (4),
  `LLM_TOTAL_CONCURRENCY` (6), `LLM_REQUESTS_PER_SECOND` (0 = tắt pacing),
  `LLM_QUEUE_TIMEOUT` (30 giây). Nếu endpoint dùng chung, đặt
  `LLM_REQUESTS_PER_SECOND` = 1–2 để tránh quá tải.
- `CHATBOT_BACKEND_URL` phải trỏ trực tiếp tới backend (Compose:
  `http://backend:8001`). Các operation `/internal/chat/lms-query` xác định
  student/course từ session đã lưu và kiểm tra lại enrollment, teacher lock,
  assignment/attempt context hiện hành.
- Một model Qwen dùng chung cho cả chat lẫn ingest nhưng có hai lane worker
  riêng: query luôn được ưu tiên, ingest gom transcript thành batch tối đa 8
  (cửa sổ 10 ms) và chạy nền trong lúc VLM xử lý các slide kế tiếp.
- Ingest mở/parse PDF một lần cho mỗi lesson, render + VLM song song theo
  `VLM_INGEST_CONCURRENCY` (mặc định 4, cũng là số thread của `Ingestion`).
  `EMBEDDING_NUM_THREADS` (mặc định 4) phải khớp CPU quota container.

## Lint

```bash
cd services/chatbot
.venv/bin/ruff check app scripts
```

## Test

```bash
./scripts/test_chatbot.sh fast    # ingest/retrieval/query, mock VLM/embedding/LLM
./scripts/test_chatbot.sh smoke   # upload → ingest → chat → cleanup trên stack thật
```

Smoke cần backend/chatbot/worker đang chạy và `LLM_*`/`VLM_*` thật; dùng user
seed `teacher@school.edu.vn` / `student@school.edu.vn`.

Script đánh giá: `scripts/eval_chatbot.py` (xem `eval/README.md`).
