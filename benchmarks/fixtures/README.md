# Benchmark fixtures

- `chat_questions.template.jsonl`: 19 câu hỏi cố định cho query/SSE benchmark.
  Placeholder `__COURSE_ID__`, `__LESSON_ID__` được thay bằng ID trong
  `fixtures.json` lúc chạy.
- `lecture_20p.pdf`: sinh tại runtime bởi `benchmarks/lib/gen_fixtures.py`
  (pymupdf, metadata cố định, 20 trang, hash deterministic). File PDF không
  commit.
- Ảnh mặt dùng `services/gaze/tests/fixtures/face_sample.jpg` (CC0).

Sinh lại PDF:

```bash
docker compose ... exec -T --user root chatbot \
  python /bench/lib/gen_fixtures.py --out /bench/fixtures/lecture_20p.pdf
```
