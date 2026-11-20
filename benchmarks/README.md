# Benchmark baseline — GazeEdu / EyeLearning

Bộ harness này đo hiệu năng **bản production build** trên một stack Docker cô
lập, ghi kết quả JSON/Markdown vào `benchmarks/baseline/<run-id>/` để so sánh
trước/sau khi tối ưu.

## Nguyên tắc

- Không đo `next dev`, không dùng `uvicorn --reload`.
- Không chạy trên database production. Stack benchmark dùng project
  `eyelearning-bench`, DB `eyetracking_bench`, Redis riêng, port riêng.
- Mọi script phải ghi artifact; không chỉ in ra stdout.
- Giữ nguyên model/LLM/VLM/GPU giữa baseline và after. Nếu đổi provider, ghi
  rõ và không so sánh trực tiếp.
- Nginx giới hạn `20 r/s/IP` (`api_rl`). Đo capacity trực tiếp backend
  (`:8101`), đo user-facing qua nginx (`:3100`) ở mức dưới ngưỡng.

## Cổng của stack benchmark

| Dịch vụ | Cổng host |
|---|---|
| nginx | `127.0.0.1:3100` |
| backend | `127.0.0.1:8101` |
| chatbot | `127.0.0.1:8102` |
| postgres | `127.0.0.1:5436` |
| redis | `127.0.0.1:6380` |
| gaze | không publish; chạy script qua `docker compose exec` |

## Lệnh nhanh

```bash
# Kiểm tra môi trường, không khởi động gì
./benchmarks/preflight.sh

# Chạy toàn bộ, scale nhỏ, ít mức tải
./benchmarks/run_all.sh --quick --scale tiny

# Baseline đầy đủ (4–6 giờ tuỳ máy)
./benchmarks/run_all.sh --scale baseline

# Chỉ một phần
./benchmarks/run_all.sh --only backend,db --scale tiny --quick
./benchmarks/run_all.sh --only gaze --scale tiny --quick
./benchmarks/run_all.sh --only chatbot --scale tiny --quick
```

`run_all.sh` tự build image production, khởi động stack cô lập, seed dữ liệu,
sinh token, chạy các nhóm đo và tổng hợp báo cáo. Cờ hữu ích:

| Cờ | Ý nghĩa |
|---|---|
| `--profile single\|prod` | 1 replica mỗi service hoặc giống production |
| `--scale tiny\|baseline\|stress` | Quy mô dữ liệu seed |
| `--quick` | Ít mức tải, duration ngắn, 1 repeat |
| `--skip-build` | Dùng image đã build |
| `--skip-seed` | Dùng DB đã seed |
| `--only a,b,c` | Chỉ chạy nhóm: `preflight,up,fixtures,seed,tokens,backend,db,frontend,gaze,chatbot,report` |
| `--run-id <id>` | Tên thư mục kết quả |
| `--keep` | Không dừng stack sau khi chạy |

## Cấu trúc kết quả

```text
benchmarks/baseline/20261121T140000Z-baseline/
  meta.json
  env/
    cpu.txt  mem.txt  gpu.txt  docker.txt  git.txt  env.txt
  fixtures.json                  # ID + row counts, không chứa token
  .runtime/tokens.json           # gitignored, chứa access token benchmark
  backend/
    endpoints.json  endpoints.md
    k6/*.json
    pg_stat_statements/*.csv
    explain/*.txt
    redis/*.txt
  frontend/
    bundle-size.json  bundle-size.md
    lighthouse/*.json
    lighthouse-summary.json
  gaze/
    stage-latency.json
    ws-load.json
  chatbot/
    ingest.json
    query.json
    components.json
  summary.json
  summary.md
```

`benchmarks/baseline/latest` là symlink tới run gần nhất (nếu hệ thống cho
phép tạo symlink).

## So sánh trước/sau

```bash
python benchmarks/report/compare.py \
  --baseline benchmarks/baseline/20261121T140000Z-baseline \
  --after    benchmarks/baseline/20261122T090000Z-after \
  --out      benchmarks/baseline/compare.md
```

## Công cụ host

- k6: mặc định dùng Docker image `grafana/k6:0.57.0` (`K6_IMAGE` để đổi).
- Lighthouse: cần `lighthouse` + Chrome/Chromium trên host. Nếu thiếu, nhóm
  frontend vẫn đo bundle và bỏ qua Lighthouse.
- `jq`, `curl`, `python3`, Docker Compose là bắt buộc.

## Ghi chú kỹ thuật

- **Chatbot không dùng LangGraph**; pipeline tuyến tính
  `query prep → retrieval → generation → citation gate`.
- **Vector store là pgvector** trên PostgreSQL, HNSW `idx_slides_hnsw`.
- **Ingest không chunk text**: mỗi slide PDF là một transcript/embedding.
- **Gaze calibration runtime dùng numpy `lstsq`**, không sklearn.
- **Nginx 20 r/s/IP** che capacity backend; luôn tách direct backend và nginx.
- Dữ liệu seed là synthetic, trừ khi bạn restore bản backup production đã
  sanitize. Absolute latency chỉ có ý nghĩa trên cùng dataset/cấu hình.
