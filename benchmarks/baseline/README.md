# Baseline artifacts

Mỗi lần chạy tạo một thư mục `<UTC timestamp>-<label>/`. Không sửa tay file
JSON; dùng `benchmarks/report/compare.py` để so sánh.

- `summary.json` / `summary.md`: bảng tổng hợp.
- `fixtures.json`: ID và row counts của dataset; không chứa token.
- `.runtime/`: token/cookie tạm, đã gitignore.
- `backend/`, `frontend/`, `gaze/`, `chatbot/`: artifact chi tiết.

Chỉ commit các file JSON/Markdown nhỏ. Dump DB, log Postgres, Lighthouse HTML
và file PDF fixture nằm ngoài Git.
