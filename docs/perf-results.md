# Kết quả benchmark sau 10 phase — GazeEdu / EyeLearning

> Nguồn: `benchmarks/baseline/20261120T180000Z-baseline` (trước tối ưu) và
> `benchmarks/baseline/20261122T1640Z-after-10phase` (sau 10 phase, code hiện tại).
> Commit final: `f3c5f1e` (nhánh `improve_perform`, sau `9e60f53` + `d41d264`).
> Stack `eyelearning-bench` cô lập, profile `single`, scale `baseline`, cờ `--quick`.
> Host: 12 core, 30 GiB RAM, RTX 3060 12 GiB; PostgreSQL 16 + pgvector, Redis 7.
> Chi tiết thay đổi và gate từng đợt: `docs/perf-roadmap.md`. Audit gốc: `docs/perf-audit.md`.

## 0. Cách đọc báo cáo

- Hai run dùng **cùng** profile/scale/quick nên so trực tiếp được. Baseline chạy
  commit `e7f0c25` (trước mọi tối ưu); final chạy `f3c5f1e` (sau Phase 1–10 và
  fix đồng bộ layout chat AOI).
- Dataset hai run giống nhau: **19.240 `content_views`**, **3.445.200
  `gaze_samples`**, 540 slide, 202 user, 1.057 `learning_sessions`.
- `--quick` = 10 s/scenario, 5 VU read / 2 VU heavy / 8 VU gaze write, 1 repeat.
  Dùng để so **tương đối**; p99 và các ca 1 phiên có phương sai cao, không dùng
  làm SLO tuyệt đối.
- Lighthouse bị bỏ qua (host không có binary); nhóm frontend vẫn đo bundle
  production và capture gaze client.
- Artifact trung gian của từng phase đã được dọn (xem §12). Số liệu lịch sử
  từng đợt vẫn nằm trong `docs/perf-roadmap.md` kèm run-id gốc.
- Bảng delta đầy đủ 289 metric do harness sinh:
  `benchmarks/baseline/20261122T1640Z-after-10phase/report/compare-baseline.md`.

## 1. Tóm tắt điều hành

| # | Khu vực | Chỉ số chốt | Baseline | Sau 10 phase | Gate | Kết quả |
|---:|---|---|---:|---:|---|---|
| 1 | Analytics | `aoi_summary` p50/p95 | 1.249 / 1.308 s | **184 / 223 ms** | ≤200 / ≤300 ms | Đạt |
| 1 | Analytics | `aoi_summary` rps | 1,38 | **5,12** | ≥5 | Đạt |
| 2 | Chat | TTFT p95 1 VU / 5 VU | 34,7 / 35,7 s | **0,76 / 0,37 s** | ≤5 / ≤10 s | Đạt |
| 2 | Chat | Total p95 1 VU / 5 VU | 63,6 / 64,0 s | **8,03 / 10,73 s** | ≤25 s | Đạt |
| 2 | Chat | error rate 5 VU | 12,5% | **0%** | 0 | Đạt |
| 3 | Gaze realtime | 8 phiên: drop / p95 | 10,08% / 145 ms | **0% / 21,1 ms** | ≤2% / ≤80 ms | Đạt |
| 3 | Gaze realtime | fps/phiên, resp/s (8 phiên) | 13,49 / 107,9 | **15,0 / 120,0** | ≥14,5 / ≥115 | Đạt |
| 4 | RAG ingest | 2 slide wall | 25,44 s | **7,41 s** | ≤12 s | Đạt |
| 4 | RAG ingest | embedding p95 / VLM p95 | 8,16 / 10,74 s | **2,04 / 3,28 s** | ≤2 s / ≤11,8 s | Sát ngưỡng (embedding +2%) |
| 5 | Gaze write | `gaze_batch` 8 VU p50/p95 | 36,2 / 53,1 ms | **9,2 / 27,8 ms** | ≤15 / ≤25 ms | p50 đạt, p95 sát ngưỡng |
| 5 | Gaze write | `analyze_lesson` 54k sample | 54k/txn † | **1,46 s**, txn max 134 ms | ≤15 s, ≤2 s | Đạt |
| 6 | Export | page p95 (100k) / total | 21,2 ms † / – | **2,5 ms / 1,55 s** | ≤100 ms / ≤10 s | Đạt |
| 6 | Retention | 1 DELETE → batch 10k | 1 txn 4,45M † | **459 batch**, txn max 96 ms | ≤10k/batch, ≤2 s | Đạt |
| 7 | Retrieval | dense SQL p50 / recall@8 | 1,75 ms / – | **1,40 ms / 1,0** | SQL ≤5 ms, recall giữ 1,0 | Đạt |
| 8 | Read model | `teacher_courses` p95 | 45,5 ms | **12,8 ms** | ≤20 ms | Đạt |
| 8 | Read model | `course_visits` / `replay` p95 | 70,8 / 60,5 ms | **19,7 / 25,5 ms** | ≤60 / ≤50 ms | Đạt |
| 8 | Read model | `course_students` payload | 442 KB † | **23,2 KB** | ≤150 KB | Đạt |
| 9 | Access/cache | auth Redis GET/request | 1 † | **0** | 0 | Đạt |
| 9 | Access/cache | add 200 SV p95 | – | **52,1 ms** | ≤300 ms | Đạt |
| 9 | Nginx | gaze-batches 30 HS p95 | – | **67,7 ms** | ≤60 ms | Chưa đạt tuyệt đối |
| 10 | Capture | capture+encode p95 | 8,9 ms † (main thread) | **8,8 ms** (worker) | ≤10 ms, 0 long task | Đạt |
| 10 | Capture | bytes/frame (JPEG) | 33,2 KB † (q0,90) | **20,4 KB** (q0,78) | ≤25 KB | Đạt |
| 10 | Capture | WS bandwidth | 100% † | **~61%** | ≤50% | Không đạt (trade-off accuracy) |

† Ô baseline lấy từ run baseline **của phase tương ứng** (artifact đã dọn, số nằm
trong `docs/perf-roadmap.md`), vì run baseline gốc chưa có probe/cấu hình đó.
Cold retrieval p95 440 → 452 ms chỉ có trong roadmap Phase 7 (baseline
`phase4-final`), không đo lại ở run final; xem §7.

Kết luận ngắn: **10/10 phase đã chốt**, không có hồi quy ở luồng nghiệp vụ; 4
điểm chưa đạt tuyệt đối đều là ngưỡng biên đã biết trước và được ghi trong
roadmap: p95 nginx gaze (67,7 vs 60 ms), `gaze_batch` p95 quick (27,8 vs 25 ms),
embedding p95 (2,04 vs 2,0 s), bandwidth capture (61% vs 50%).

## 2. Backend API (k6, quick)

| Scenario | p50 base | p50 after | p95 base | p95 after | Δ p95 | rps base | rps after |
|---|---:|---:|---:|---:|---:|---:|---:|
| `enrollments` | 8,20 | 4,40 | 11,86 | **7,31** | −38,4% | 23,77 | 24,03 |
| `outline` | 15,44 | 8,01 | 20,95 | **13,45** | −35,8% | 23,28 | 23,64 |
| `lesson_contents` | 16,80 | 10,80 | 34,49 | **19,09** | −44,7% | 22,78 | 23,53 |
| `session_contents` | 14,55 | 11,50 | 34,79 | **18,58** | −46,6% | 22,91 | 23,32 |
| `teacher_courses` | 33,41 | 8,07 | 45,51 | **12,76** | −72,0% | 8,57 | 9,54 |
| `course_visits` | 35,58 | 13,18 | 70,75 | **19,69** | −72,2% | 20,73 | 23,11 |
| `replay` | 53,42 | 15,22 | 60,53 | **25,52** | −57,8% | 7,96 | 9,26 |
| `samples` | 18,34 | 19,32 | 30,55 | **27,14** | −11,2% | 22,57 | 22,55 |
| `aoi_summary` | 1.249,25 | 184,30 | 1.307,93 | **222,60** | −83,0% | 1,38 | 5,12 |
| `gaze_batch` (8 VU) | 36,18 | 9,22 | 53,08 | **27,79** | −47,6% | 7,69 | 7,89 |

Scenario chỉ có ở run final (thêm trong Phase 9, không có baseline tương ứng):

| Scenario | p50 | p95 | rps | error |
|---|---:|---:|---:|---:|
| `auth-me` (1 VU) | 7,74 | 9,88 | 4,80 | 0 |
| `course_students` | 7,76 | 15,87 | 23,68 | 0 |
| `add-students` (200 SV) | 28,54 | 52,10 | 4,32 | 0 |
| `gaze_batch_nginx` (30 HS sau NAT) | 12,89 | 67,66 | 19,61 | 0 |

- `samples` gần như phẳng (p95 −11%) vì response vẫn phải trả 1 trang sample
  keyset; chi phí nằm ở serialize chứ không phải SQL (page p95 11,5 ms ở §6).
- `gaze_batch` và `gaze_batch_nginx` là hai scenario nặng nhất còn lại; đây là
  trần backend khi 8/30 VU bắn cùng nhịp, không phải lỗi nginx (direct backend
  cùng tải tương đương).

## 3. Query trên mỗi request

Đếm bằng `pg_stat_statements` trong 20 request/scenario:

| Endpoint | base q/req | after q/req | Δ |
|---|---:|---:|---:|
| `replay` | 15,25 | **8,05** | −47,2% |
| `course_students` | 12,80 | **8,15** | −36,3% |
| `session_contents` | 13,25 | **11,60** | −12,5% |
| `course_visits` | 9,20 | **8,65** | −6,0% |
| `teacher_courses` | 9,25 | **8,70** | −5,9% |
| `samples` | 11,20 | **10,95** | −2,2% |
| `aoi_summary` | 13,70 | 15,00 | +9,5% |
| `outline` | 7,30 | 8,75 | +19,9% |
| `enrollments` | 1,50 | 3,85 | +156,7% |

> **Lưu ý cách đếm:** phép đếm này gồm mọi statement trong cửa sổ đo, kể cả
> worker poll `background_jobs` và `BEGIN/ROLLBACK`. Final run có nhiều worker
> poll hơn baseline (12+12 so với 4+4 lần/20 request), nên các endpoint có ít
> query thật (`enrollments`, `outline`) bị nhiễu và trông như tăng. Số đã hiệu
> chỉnh (trừ BEGIN/ROLLBACK + worker poll) ở Phase 8/9 trong
> `docs/perf-roadmap.md`: `teacher_courses` 4,05 → 1,05; `replay` 10,05 → 3,0;
> `course_students` 7,0 → 4,05. `aoi_summary` vẫn cần 15 query/request, đây là
> chi phí cấu trúc của read path analytics và là ứng viên tối ưu tiếp theo.

## 4. Auth và cache

| Chỉ số | Baseline | Sau 10 phase |
|---|---:|---:|
| `auth-me` p95 (HTTP) | – | 9,88 ms |
| auth dependency p50/p95/p99 | Redis GET mỗi request | **0,0012 / 0,0013 / 0,0023 ms** |
| Redis GET / request (memory hit) | 1 | **0** (0/500 lần) |
| Redis hit rate trong cửa sổ | 0,9726 | 0,9527 |
| Redis commands trong cửa sổ | 1,90 M | 7,1 k |

Redis hit rate thấp hơn nhẹ là do cửa sổ đo khác nhau (baseline tích luỹ từ
seed + load cũ, final đo trên Redis vừa truncate); điểm quan trọng là **0 GET
khi memory hit**, tức auth không còn round-trip Redis trên hot path.

## 5. Gaze realtime (WebSocket + stage)

| Phiên | p95 base | p95 after | drop base | drop after | fps/phiên base | fps/phiên after |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 45,0 ms | 45,9 ms | 2,00% | 5,33%* | 14,7 | 14,2 |
| 4 | 29,2 ms | 30,0 ms | 3,17% | 1,17% | 14,53 | 14,82 |
| 8 | 145,5 ms | **21,1 ms** | 10,08% | **0%** | 13,49 | **15,0** |

\* Ca 1 phiên trong quick chỉ có 10 s (~150 frame); 3–8 frame bị throttle đã là
5%. Ca 4 và 8 phiên — đúng gate — đều giảm, 8 phiên drop 0%.

| Stage | 480px p50/p95 | 720px p50/p95 | 1080px p50/p95 |
|---|---:|---:|---:|
| Baseline (fp32) | 10,96 / 11,33 ms | 11,68 / 12,41 ms | 13,19 / 13,33 ms |
| After (fp16) | **6,59 / 6,93 ms** | **7,20 / 7,81 ms** | **8,56 / 9,20 ms** |

- VRAM giảm **346 → 212 MiB** nhờ fp16; RSS tiến trình không đổi (~1,30 GiB).
- Payload client 480px/q0,78 (giống browser thật): p95 48,5 ms ở 8 phiên,
  drop 0%. Con số cao hơn payload server mặc định do harness đo RTT 8 client
  trong cùng container, không phải regression server (xem Phase 10).
- Độ chính xác khi chuyển fp32 → fp16 và đổi payload đã được A/B ở Phase 3/10;
  quyết định giữ **480px/q0,78**.

## 6. Gaze write, analysis, export, retention

`gaze_batch` (8 VU, 40 sample/batch) và probe worker:

| Chỉ số | Baseline | Sau 10 phase | Gate |
|---|---:|---:|---|
| `gaze_batch` p50 / p95 | 36,2 / 53,1 ms | **9,2 / 27,8 ms** | ≤15 / ≤25 ms |
| `analyze_lesson` 54k sample: wall | 54k row/txn | **1,46 s** | ≤15 s |
| transaction lớn nhất | toàn bộ 54k | **134 ms** | ≤2 s |
| peak RSS worker | – | **77,6 MiB** | ≤512 MiB |
| checksum metrics/AOI/heatmap | `8e9baa04…` | **`8e9baa04…`** | giống hệt |

Checksum trùng với Phase 5 nghĩa là tối ưu không đổi kết quả phân tích
(`gaze-metrics-v8`). Cột **Baseline** của bảng trên lấy từ probe trước tối ưu ở
Phase 5 (run đã dọn); final đo lại bằng `analysis_probe.py` trong run này.

Export JSONL và page gaze:

| Case | Page p50/p95 | Total | RSS Δ | Ghi chú |
|---|---:|---:|---:|---|
| 100k sample, 1 export | 2,18 / **2,49 ms** | **1,55 s** | +1,2 MiB | 120 page |
| 100k sample, 5 export đồng thời | 9,69 / **34,76 ms** | 7,72 s | – | 0 `idle in transaction` |
| 29.377 sample (visit thật) | 2,04 / **2,35 ms** | **0,47 s** | +0,9 MiB | 40 page |
| `/teacher/visits/{id}/gaze` offset 50k | 10,82 / **11,52 ms** | – | – | keyset, không seq scan |

Retention (`maintenance_probe`, batch 10k): xoá **4.445.200** row trong **459
commit**, transaction lớn nhất **96 ms**, lock wait **0 ms**, p95 insert gaze
trong lúc xoá **4,21 ms** (so với chính `insert_baseline` **14,74 ms**). Gate
Phase 6 đạt.

## 7. Chatbot / RAG

| Luồng | Concurrency | TTFT p95 base | TTFT p95 after | Total p95 base | Total p95 after | Error base → after |
|---|---:|---:|---:|---:|---:|---|
| Chatbot trực tiếp | 1 | 34.692 ms | **759 ms** | 63.613 ms | **8.029 ms** | 0 → 0 |
| Chatbot trực tiếp | 5 | 35.655 ms | **368 ms** | 64.050 ms | **10.726 ms** | 12,5% → **0%** |
| Qua backend | 1 | 15.674 ms | **190 ms** | 35.133 ms | **4.956 ms** | 0 → 0 |
| Qua backend | 5 | 45.126 ms | **365 ms** | 71.413 ms | **7.970 ms** | 0 → 0 |

- `verified=true` giữ **8/8** câu trả lời có citation; không có
  `citation_gate_failed`.
- Ingest 2 slide: wall **25,44 s → 7,41 s**; VLM p95 **10,74 → 3,28 s**;
  embedding p95 **8,16 → 2,04 s**; `db_upsert` p95 16,8 → 3,6 ms.
- Retrieval: recall@8 **1,0**, MRR **1,0** (ANN và exact trùng top-8); dense SQL
  p50 **1,75 → 1,40 ms**; ANN p50 0,98 ms (`plan_uses_hnsw=false` — planner chọn
  filter-first + top-N heapsort 120 row, đúng kết luận Phase 7). Cold retrieval
  p95 (gồm embedding) **440,3 → 452,0 ms** chỉ có trong roadmap Phase 7
  (baseline `20261121T1135Z-phase4-final`); run final không đo lại cold,
  nhưng SQL vẫn ~1,4 ms nên phần tăng nằm ở embedding, không phải query.
- Ingest 100 slide (gate ≤6 phút) không chạy lại trong run final vì cần
  `BENCH_INGEST_SLIDES=100`; số cũ **206,98 s (3,45 phút)** vẫn hiệu lực vì
  Phase 10 chỉ đổi phía client capture.

## 8. Frontend

| Chỉ số | Baseline | Sau 10 phase | Δ |
|---|---:|---:|---:|
| Bundle static raw | 4.143.473 B | 4.149.876 B | +0,15% |
| Bundle static gzip | 2.005.967 B | 2.008.426 B | +0,12% |
| Trang `/` jsGzip | 55.371 B | 55.371 B | 0% |
| Trang `/teacher` jsGzip | 101.377 B | 101.427 B | +0,05% |

Bundle gần như không đổi — đúng kỳ vọng, Phase 10 tối ưu đường capture chứ
không cắt bundle. Lighthouse: **chưa đo** (thiếu binary trên host).

Capture gaze client (150 frame, 15 fps, Chromium headless, 640×480):

| Đường | p50 | p95 | max | bytes p95 | long task >50 ms | PSNR |
|---|---:|---:|---:|---:|---:|---:|
| Worker (OffscreenCanvas + worker encode) | 8,2 ms | **8,8 ms** | 28,9 ms | 6.913 B | **0** | 99 dB |
| Legacy (main thread drawImage + toBlob) | 7,5 ms | 8,6 ms | 12,2 ms | 6.869 B | 0 | – |

A/B width × quality có calibration thật (giữ 480/q0,78 làm chuẩn):

| Biến thể | JPEG bytes | Δ pose | Δ px | Gate | Kết luận |
|---|---:|---:|---:|---|---|
| 480 / q0,78 | 20.387 B | 0% | 0% | – | **Giữ** |
| 480 / q0,70 | 16.571 B | **12,4%** | 6,9% | Δpose ≤5% | Fail |
| 320 / q0,70 | 8.328 B | **28,0%** | **16,2%** | Δpose ≤5%, Δpx ≤10% | Fail |

Đánh đổi đã chốt: JPEG bằng **~61% baseline q0,90** (20,4 KB so với 33,2 KB)
nhưng **không đạt mục tiêu ≤50% bandwidth**; giảm tiếp phải mở đợt riêng cho
320px + calibration cùng format.

## 9. DB và kế hoạch truy vấn

- `EXPLAIN` của 11 truy vấn nóng nằm ở `backend/explain/` của run final:
  `aoi_summary` gồm 3 statement **14,2 / 14,5 / 100,0 ms**; statement 14,2 ms
  sort 9.700 row ≈ 4,2 MB, statement 100,0 ms là `GroupAggregate` 1.203 nhóm.
  Export dùng `Index Scan using idx_gaze_samples_view_time` + Incremental Sort,
  không seq scan; retrieval dense là filter-first + top-N heapsort.
- Với `aoi_summary` p95 223 ms, SQL chiếm khoảng 129 ms; phần còn lại là
  Python/Pydantic + payload. Muốn xuống dưới 150 ms phải cắt statement 100 ms
  (group theo AOI) chứ không phải tối ưu ORM.
- Không có migration mới nào phát sinh trong 10 phase ngoài `006_gaze_sample_indexes.sql`
  (BRIN `event_time`), đúng bất biến schema generation 13.

## 10. Diễn biến theo phase (tóm tắt)

| Phase | Thay đổi chính | Kết quả chốt |
|---:|---|---|
| 1 | Analytics read path hẹp, aggregate xuống SQL | `aoi_summary` 1.308 → 221 ms |
| 2 | Chat stream sớm, tách pool embedding, cache rewrite | TTFT p95 34,7 → 1,77 s |
| 3 | GPU queue/batch xuyên session, fp16 | 8 phiên drop 10,1% → 0%, p95 19,1 ms |
| 4 | Bỏ lock ingest, batch embedding/VLM | 2 slide 25,4 → 9,2 s; 100 slide 207 s |
| 5 | Bỏ write amplification, chunk metrics | gaze p95 53 → 16,6 ms; 54k/txn → 127 ms/txn |
| 6 | Keyset export, batch retention | page p95 21 → 2,4 ms; 1 DELETE → 459 batch |
| 7 | Retrieval 2 vòng, bỏ threshold khỏi WHERE | cold p95 440 → 452 ms, recall 1,0 |
| 8 | Read model DTO + gộp round-trip | `teacher_courses` 45,5 → 12,8 ms |
| 9 | Auth memory-first, cache access, zone nginx | 0 Redis GET, `course_visits` 55,7 → 19,2 ms |
| 10 | Capture worker, JPEG q0,78 | p95 8,8 ms, 20,4 KB/frame, accuracy giữ |

Số trong bảng là **tại thời điểm phase**, đo trên run riêng của phase đó, nên có
thể lệch vài % so với run final ở §2–§8 (ví dụ `gaze_batch` p95 16,6 ms ở Phase 5
so với 27,8 ms ở run final do phương sai `--quick` và tải chạy chung). Khi cần số
chuẩn để so sánh, dùng bảng ở §1–§8 của báo cáo này.

Số chi tiết từng đợt kèm run-id gốc: `docs/perf-roadmap.md`.

## 11. Chưa đạt và việc tiếp theo

1. **Nginx gaze-batches**: p95 67,7 ms khi 30 HS cùng nhịp 1,5 s (gate 60 ms).
   Overhead nginx ~0; muốn giảm cần jitter client hoặc tăng worker/pool.
2. **`gaze_batch` p95 quick**: 27,8 ms (gate 25 ms) — phương sai keep-alive
   16–41 ms giữa các run; đo full trước khi kết luận regression.
3. **Embedding ingest p95**: 2,04 s/slide, sát gate 2,0 s; muốn chắc cần batch
   lớn hơn hoặc GPU riêng cho embedding.
4. **`aoi_summary`**: p95 223 ms, 15 query/request; còn dư địa cache/CTE.
5. **Bandwidth capture**: 61% so với 50% mục tiêu; cần đợt 320px + calibration.
6. **`enrollments`/`outline` query count**: nhiễu worker poll; nếu cần số sạch
   thì sửa harness đếm (lọc statement hạ tầng) trước khi đặt gate mới.
7. **Lighthouse**: chưa có trên host; cài `lighthouse` + Chrome rồi chạy
   `benchmarks/frontend/lighthouse.sh` để có LCP/TBT.

## 12. Artifact và dọn dẹp

Chỉ giữ hai run trong `benchmarks/baseline/`:

| Run | Vai trò | Kích thước |
|---|---|---:|
| `20261120T180000Z-baseline` | Baseline gốc trước tối ưu, nguồn của `perf-audit.md` | 4,8 MB |
| `20261122T1640Z-after-10phase` | Kết quả sau 10 phase trên code hiện tại | 1,2 MB |

Đã xoá **21 run trung gian**: `phase1`, `phase2`, `phase3-quick`, `phase3-full`,
`phase3-final-quick`, `phase4`, `phase4-100`, `phase4-final`, `phase5`, `phase51`,
`phase6`, `phase7`, `phase7-final`, `phase8`, `phase9` ×2, hai run baseline dở
(`045443Z-baseline`, `062123Z-baseline`) và bộ `pre/post/post2-chat-layout`;
kèm 2 file `compare-*.md` cũ. Lịch sử vẫn khôi phục được bằng
`git checkout <commit> -- benchmarks/baseline/<run-id>`.

Hai artifact không tự sinh lại trong run final được bảo toàn:

- `backend/analysis_probe.json`, `export_probe_100k.json`,
  `export_probe_29k.json`, `maintenance_probe.json` — chạy tay sau `run_all`
  bằng `docker compose exec`, xem §13.
- `gaze/capture-ab-calibrated.json` — chép từ run `20261122T062123Z-baseline`
  (cùng harness, cùng code capture; probe hiện tại không có file calibration
  UBJ). Nguồn ghi rõ trong `gaze/README.md` của run.

## 13. Tái lập

```bash
# 1. Run chính (build production image, seed baseline, k6 + gaze + chatbot + frontend)
./benchmarks/run_all.sh --quick --scale baseline \
  --run-id 20261122T1640Z-after-10phase --keep

# 2. Probe worker/export/retention (stack còn sống nhờ --keep)
RUN=20261122T1640Z-after-10phase
DC="docker compose -p eyelearning-bench --env-file .env \
  -f docker-compose.yml -f benchmarks/stack/docker-compose.bench.yml"
$DC exec -T backend python /bench/backend/analysis_probe.py \
  --samples 54000 --chunk-size 3000 \
  --out /bench/baseline/$RUN/backend/analysis_probe.json
$DC exec -T backend python /bench/backend/export_probe.py \
  --samples 100000 --concurrency 5 \
  --out /bench/baseline/$RUN/backend/export_probe_100k.json
$DC exec -T backend python /bench/backend/export_probe.py \
  --samples 29377 --concurrency 1 \
  --out /bench/baseline/$RUN/backend/export_probe_29k.json
$DC exec -T backend python /bench/backend/maintenance_probe.py \
  --old-samples 1000000 --batch-size 10000 \
  --out /bench/baseline/$RUN/backend/maintenance_probe.json

# 3. Tổng hợp + so sánh
python3 benchmarks/report/summarize.py --run-dir benchmarks/baseline/$RUN
python3 benchmarks/report/compare.py \
  --baseline benchmarks/baseline/20261120T180000Z-baseline \
  --after benchmarks/baseline/$RUN \
  --out benchmarks/baseline/$RUN/report/compare-baseline.md
```

Lưu ý thứ tự: `maintenance_probe` xoá gaze cũ trong DB bench nên phải chạy
**sau cùng**; muốn đo lại trajectory/replay sau đó thì seed lại dataset.
