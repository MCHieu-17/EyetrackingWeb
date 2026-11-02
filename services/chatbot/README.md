# Chatbot service (RAG hỗ trợ học tập)

FastAPI + LangChain: ingest slide bằng VLM → hybrid retrieval (pgvector + Postgres
FTS) → sinh câu trả lời → verify citation → SSE.

## Endpoints

| Method | Path | Auth | Mục đích |
|---|---|---|---|
| GET | `/health` | – | Liveness, luôn 200 |
| GET | `/ready` | – | Readiness, 503 khi DB không truy cập được |
| POST | `/chat` | `X-Chatbot-Token` | Hỏi đáp non-streaming |
| POST | `/chat/stream` | `X-Chatbot-Token` | SSE: status → citations → token → done |
| POST | `/ingest/slide` | `X-Chatbot-Token` | Embed 1 slide |
| POST | `/ingest/lesson` | `X-Chatbot-Token` | Embed toàn bộ slide của bài |
| POST | `/ingest/course` | `X-Chatbot-Token` | Embed toàn bộ slide của khóa |
| POST | `/ingest/reindex-all` | `X-Chatbot-Token` | Backfill slide chưa ready |

## Luồng xử lý

```
route (course_qa | exercise_hints | exercise_review | study_skills | out_of_scope)
  → retrieve (hybrid, chỉ trong course_id)
  → answer (DeepSeek qua River AI)
  → verify (citation + no-solution)
  → retry tối đa CITATION_MAX_ATTEMPTS
  → sanitize → SSE
```

- **Citation**: mỗi claim về môn học phải có `[n]`; verifier trả `evidence_quote`
  và code kiểm tra quote có thật trong tài liệu. Không verify được → câu an toàn.
- **Bài tập**: `exercise_hints` không lộ đáp án/lời giải; `exercise_review` được
  chữa bài vì backend chỉ gửi đáp án sau khi sinh viên đã nộp.
- **General knowledge**: phải nằm dưới label `Ngoài tài liệu môn học:` và không
  được gắn citation.
- **Streaming**: chỉ phát `token` sau khi verify xong; trước đó phát `status`.

## Cấu hình (biến môi trường)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `CHATBOT_DATABASE_URL` | – | DSN psycopg (`postgresql://...`), không dùng `+asyncpg` |
| `CHATBOT_INTERNAL_TOKEN` | – | Token nội bộ (bắt buộc) |
| `LLM_NAME` | `river` | LLM qua River AI |
| `VLM_NAME` | `river` | VLM cho ingest slide |
| `EMBEDDING_NAME` | `local` | Embedding local Qwen3-Embedding-0.6B |
| `EMBEDDING_DIM` | `1024` | Phải khớp `vector(1024)` của migration 024 |
| `EMBEDDING_MODEL_PATH` | `/app/weights/Qwen3-Embedding-0.6B` | Đường dẫn weights |
| `EMBEDDING_DEVICE` | `cuda` | `cuda` \| `cpu` |
| `EMBEDDING_LOCAL_FILES_ONLY` | `true` | Chỉ đọc weights đã tải |
| `EMBEDDING_HF_REPO` | `Qwen/Qwen3-Embedding-0.6B` | Repo HuggingFace |
| `RIVER_API_KEY` | – | API key River AI (bắt buộc) |
| `RIVER_BASE_URL` | `https://api.river.ai/v1` | Endpoint OpenAI-compatible |
| `RIVER_LLM_MODEL` | `deepseek-ai/DeepSeek-V4.1-Flash-1017` | Model LLM |
| `RIVER_VLM_MODEL` | `deepseek-ai/DeepSeek-V4.1-Flash-1017` | Model VLM |
| `RIVER_LLM_MAX_TOKENS` | `8192` | Max output cho answer |
| `RIVER_ROUTER_MAX_TOKENS` | `1024` | Max output cho router |
| `RIVER_VERIFIER_MAX_TOKENS` | `8192` | Max output cho verifier |
| `RIVER_VLM_MAX_TOKENS` | `16384` | Max output cho VLM |
| `RIVER_REASONING_EFFORT` | `low` | `low` \| `high` \| `max` \| `none` |
| `RIVER_ROUTER_REASONING_EFFORT` | `none` | Tắt reasoning cho router |
| `RIVER_VERIFIER_REASONING_EFFORT` | `none` | Tắt reasoning cho verifier |
| `RIVER_VLM_REASONING_EFFORT` | `none` | Tắt reasoning cho VLM |
| `RAG_TOP_K` | `8` | Số slide trả về |
| `RAG_CANDIDATES` | `20` | Số candidate mỗi nhánh hybrid |
| `RAG_RRF_K` | `60` | Hằng số RRF |
| `RAG_SCORE_THRESHOLD` | `0.25` | Ngưỡng cosine tối thiểu |
| `CITATION_MAX_ATTEMPTS` | `2` | Số lần sinh lại tối đa |
| `LOCAL_MEDIA_DIR` | `/app/media` | Thư mục slide local |
| `STORAGE_HTTP_ALLOWED_HOSTS` | – | Host HTTP được phép fetch slide |
| `R2_*` | – | Cloudflare R2 (nếu dùng) |

`app/settings.py` cung cấp `validate()` để fail-fast lúc khởi động nếu cấu hình
thiếu/sai.

## DB role hạn chế

Chatbot dùng role `chatbot_reader` (xem `CHATBOT_DB_USER`/`CHATBOT_DB_PASSWORD`):
- được `SELECT` course/module/lesson/slide + `INSERT/UPDATE/DELETE` embedding;
- được `UPDATE` các cột `embedding_status/embedding_error/embedding_updated_at`;
- **không** có quyền đọc `quiz_assignments`, `quiz_attempts`, `quiz_attempt_sessions`,
  `users`.

Tạo/cập nhật role sau khi migrations đã áp:

```bash
./ops/create_chatbot_role.sh
```

Đây là lớp bảo vệ thứ hai: kể cả khi prompt injection yêu cầu lộ đáp án, chatbot
cũng không đọc được bảng quiz.

## Chạy test

```bash
cd services/chatbot
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Test không cần DB/LLM thật: các node được cắm fake (mock / monkeypatch).

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
    ├── router.py           phân loại intent
    ├── retrieval.py        hybrid BM25 + vector (RRF)
    ├── answer.py           sinh câu trả lời theo intent
    ├── guardrails.py       citation + no-solution verifier
    ├── citations.py        parse/sanitize/quote matching
    ├── pipeline.py         orchestration + SSE events
    ├── prompts.py          prompt router/answer/verifier/VLM
    └── providers.py        LLM/embedding/VLM factories
```
