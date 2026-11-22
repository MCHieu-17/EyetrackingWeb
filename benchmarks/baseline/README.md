# Baseline artifacts

Mỗi lần chạy tạo một thư mục `<UTC timestamp>-<label>/`. Không sửa tay file
JSON; dùng `benchmarks/report/compare.py` để so sánh.

- `summary.json` / `summary.md`: bảng tổng hợp.
- `fixtures.json`: ID và row counts của dataset; không chứa token.
- `.runtime/`: token/cookie tạm, đã gitignore.
- `backend/`, `frontend/`, `gaze/`, `chatbot/`, `report/`: artifact chi tiết.

Chỉ commit các file JSON/Markdown nhỏ. Dump DB, log Postgres, Lighthouse HTML,
`.next/` và file PDF fixture nằm ngoài Git.

## Run đang giữ

| Run | Vai trò |
|---|---|
| `20261120T180000Z-baseline` | Baseline trước tối ưu (commit `e7f0c25`), nguồn của `docs/perf-audit.md` và `docs/perf-roadmap.md` |
| `20261122T1640Z-after-10phase` | Kết quả sau 10 phase trên code hiện tại (commit `f3c5f1e`), kèm probe worker/export/retention |

Báo cáo so sánh: `docs/perf-results.md`. Các run trung gian của từng phase đã
được dọn; số liệu lịch sử nằm trong `docs/perf-roadmap.md` kèm run-id gốc và
khôi phục được bằng `git checkout <commit> -- benchmarks/baseline/<run-id>`.

`20261122T1640Z-after-10phase/gaze/capture-ab-calibrated.json` được chép từ run
`20261122T062123Z-baseline` (cùng harness/cùng code capture) vì `run_all.sh`
không có file calibration UBJ để tái tạo `px_delta`. Nguồn ghi trong
`gaze/README.md` của run.
