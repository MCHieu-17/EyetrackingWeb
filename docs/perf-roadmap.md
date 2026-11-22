# Perf roadmap — GazeEdu / EyeLearning

> Nguồn: `docs/perf-audit.md`; baseline `benchmarks/baseline/20261120T180000Z-baseline` (quick, profile `single`).
> Kết quả tổng hợp baseline → sau 10 phase và artifact còn giữ: `docs/perf-results.md`.
> Run-id trong các mục **Kết quả benchmark** là artifact lịch sử đã dọn khỏi repo;
> khôi phục bằng `git checkout <commit> -- benchmarks/baseline/<run-id>`.
> Dataset baseline: 19.240 `content_views`, 3.445.200 `gaze_samples`, 540 `slides`.
> Nhãn `[High]/[Med]/[Low]` giữ theo audit; tài liệu này chỉ chốt thứ tự đợt và gate, không chứa code.
> Nguyên tắc: xếp theo nút thắt lớn nhất; gom thay đổi xuyên tầng vào cùng một đợt; mỗi đợt deploy/verify/rollback độc lập. Thứ tự dưới đây là thứ tự merge đề xuất.

## Quy ước verify

- Mỗi đợt chạy lại đúng scenario/scale của baseline, lưu run-id mới và so bằng `benchmarks/report/compare.py`; không so tuyệt đối giữa quick và full.
- Pass theo baseline gốc, đồng thời không regress so với run của đợt trước.
- `make check` + `make test-fast` cho mọi đợt. Đợt backend chạy `./scripts/test_backend.sh`; gaze chạy `./scripts/test_gaze.sh fast` (+ smoke nếu đổi model/preprocess); chatbot chạy `./scripts/test_chatbot.sh fast` (+ smoke nếu đổi ingest/LLM/retrieval); đổi luồng người dùng chạy `./scripts/e2e.sh`; đổi schema chạy `./scripts/test_migrations.sh`.
- Schema/index mới dùng migration mới từ `006_...sql` trở đi; không sửa `001`–`005`, không thêm bảng lõi.
- Các phép đo bổ sung ở audit §2 (backend) và §3 (gaze/chatbot) — EXPLAIN 10×, 5–10 export đồng thời, profile worker 54k sample, TTFT attribution, recall@8, A/B accuracy — là gate trước khi chốt đợt tương ứng.
- Target tuyệt đối chỉ dùng cho dataset baseline; production lớn hơn phải đo lại cùng cấu hình.
- `[x]` ở tiêu đề/tổng quan = đợt đã merge và verify; dòng **Kết quả benchmark** ghi run-id để tái lập.

## Tổng quan thứ tự

| # | Phase | Nút thắt baseline | Gate chính |
|---:|---|---|---|
| 1 | [x] Analytics dashboard | `aoi_summary` 1.249 ms, 1,38 rps | p50 ≤200 ms, p95 ≤300 ms, 2 VU ≥5 rps |
| 2 | [x] Chat TTFT & capacity | TTFT p95 34,7 s, lỗi 12,5% | TTFT p95 ≤5 s (1 VU) / ≤10 s (5 VU), lỗi 0 |
| 3 | [x] Gaze realtime | 8 phiên drop 10,1%, p95 145 ms | drop ≤2%, p95 ≤80 ms |
| 4 | [x] RAG ingest | 2 slide 25,4 s | ≤12 s; 100 slide ≤6 phút |
| 5 | [x] Gaze write + analysis | ~40 UPDATE/phút/view; 54k row/txn | `gaze_batch` p95 ≤25 ms; 0 update thừa |
| 6 | [x] Export + retention | O(n²)/page, idle transaction | page phẳng ≤100 ms; batch 10k |
| 7 | [x] Chat retrieval | cold 1.316 ms, HNSW `idx_scan=0` | cold ≤500 ms; recall không giảm; planner chọn HNSW/filter-first |
| 8 | [x] Backend read models | `teacher_courses` 45,5 ms, replay 60,5 ms | p95 hoặc p50 giảm ≥20%; query/request giảm ≥50%; payload `course_students` ≤150 KB |
| 9 | [x] Access/cache/runtime | auth Redis GET, outline 2–3 query, nginx 20 r/s | 0 Redis GET khi memory hit; 0 429 |
| 10 | [x] Gaze capture contract | JPEG main-thread, 33 KB/frame | capture ≤10 ms; ≤25 KB; accuracy không giảm |

---

## [x] Phase 1 — Analytics dashboard (`aoi_summary`)

**Mục tiêu:** Đưa dashboard Trực quan hoá từ 1,25 s xuống dưới 200 ms và không chiếm trọn worker khi có 2 người xem.

**Hạng mục:**
- `[High] backend/app/services/analytics/summary.py:132` — bỏ select full entity; chỉ lấy cột cần, không kéo `slides.embedding/transcript/content_tsv`, `content_views.heatmap_grid`, `users.password_hash`.
- `[High] backend/app/services/analytics/summary.py:228` — bound thời gian + limit/keyset; đẩy aggregate `aoi_stats` xuống SQL/cache, không load toàn bộ view vào RAM.
- `[High] backend/Dockerfile:54` + `docker-compose.yml:253` — tăng worker lên 4, giảm pool/worker; chỉ chốt sau khi query đã nhẹ.
- `[Med] summary.py:180,531` (heatmap `EXISTS`) + `summary.py:204` (`_slide_names`) — dọn cùng read path, không tách đợt riêng.

**Pass:**
- `aoi_summary` p50 ≤200 ms, p95 ≤300 ms ở 2 VU; rps ≥5 (baseline `1249/1308 ms`, `1,38 rps`).
- DB mean exec ≤100 ms (baseline `590 ms`); payload đọc từ DB giảm ≥80% (không còn các cột nêu trên).
- 4 VU: p95 ≤500 ms, error 0, không pool timeout; `heatmap` p95 ≤200 ms.
- Response schema/camelCase không đổi; nếu buộc thêm `from/to` hoặc phân trang thì FE dashboard nằm trong cùng đợt; `test_backend.sh` pass.

**Kết quả benchmark:** `aoi_summary` p50/p95 **1.249/1.308 s → 186/221 ms**, **1,38 → 5,14 rps**, error 0 (run `20261121T0600Z-phase1`, quick/baseline).

**Lưu ý:** Phase 8 dùng lại read path này; giữ select cột hẹp (không kéo `embedding/transcript/heatmap_grid`) để không tái tạo nút thắt.

---

## [x] Phase 2 — Chat TTFT & capacity

**Mục tiêu:** Chat trả token đầu trong vài giây, không retry cả câu, không lỗi khi 5 người chat đồng thời.

**Hạng mục:**
- `[High] services/chatbot/app/workflow/pipeline.py:105-152` — bỏ gate buffer 200 từ/retry toàn bộ; gate trên marker citation, phát token sớm, hậu kiểm citation.
- `[High] services/chatbot/app/workflow/embedding_queue.py:37,61-98` — tách pool query khỏi ingest; query không xếp sau batch 8 × ~8 s.
- `[High] services/chatbot/app/workflow/providers.py:75-82` + `services/chatbot/app/services/ingest.py:91` — hợp nhất cache model embedding, chỉ còn một instance/worker.
- `[High] services/chatbot/app/workflow/query.py:59-71,82-104` — cache rewrite/HyDE theo câu hỏi + hash history; timeout 2–3 s + fallback; chỉ HyDE khi thật mơ hồ.
- `[Med] pipeline.py:157` + `lms.py:53-54`; `backend/app/services/chat_transport.py:56` — bỏ `check_access` trùng / cache access 30 s.
- `[Med] services/chatbot/app/api/chat.py:27-31` + `workflow/llm.py:54-98` — cân slot 20/4, trả 429 sớm thay vì giữ slot 30 s.

**Pass:**
- Chatbot trực tiếp: TTFT p95 ≤5 s (1 VU), ≤10 s (5 VU); total p95 ≤25 s; error 0 ở 5 VU (baseline `34,7/35,7 s`, `63,6/64,0 s`, `12,5%`).
- Qua backend: TTFT p95 ≤8 s (1 VU), ≤15 s (5 VU); total p95 ≤30 s; error 0.
- `verified=true` ≥ baseline; `citation_failed` không tăng; `citation_gate_failed` = 0.
- Chatbot RSS ≤1,0 GiB (baseline `1,53 GiB`); 1 embedding model; 0 queue timeout khi ingest+chat đồng thời; access check ≤1 lần/30 s stream.
- `test_chatbot.sh fast` + `test_chat.py`; `E2E_CHAT=1 ./scripts/e2e.sh`.

**Kết quả benchmark:** chatbot trực tiếp TTFT p95 1 VU/5 VU **34,7/35,7 s → 1,77/0,34 s**, total p95 **63,6/64,0 s → 7,76/8,81 s**, error **12,5% → 0%**, verified 8/8 (run `20261121T0818Z-phase2`).

**Lưu ý:** Phase 4 nâng VLM ingest lên 4 slot; Phase 7/9 khi đo chat/retrieval phải kiểm tra lại 429 và p95 của provider dùng chung.

---

## [x] Phase 3 — Gaze realtime

**Mục tiêu:** 8 phiên gaze đồng thời không drop, p95 thấp; chỉ bật fp16 sau A/B accuracy.

**Hạng mục:**
- `[High] services/gaze/app/services/runtime.py:205-207,370-372` — GPU queue sâu 2–4, batch xuyên session; CPU không block chờ GPU.
- `[High] services/gaze/app/services/pipeline.py:178,188` — batch N frame/forward, copy output một lần, `non_blocking`/pinned buffer.
- `[High] docker-compose.yml:539` — A/B fp16, giữ fp32 làm fallback theo model.
- `[High] docker-compose.yml:516-517,554` — một replica/GPU + batch nội bộ; không đặt 2 replica cùng một card.
- `[Med] runtime.py:309-314` — cancel job timeout trước forward; `runtime.py:101-124,167-179` — stats lock/EMA.
- `[Med] services/gaze/app/api/session.py:233-236,263` — throttle sau parse, sender task riêng; `services/gaze/app/services/sessions.py:78-84` — touch TTL khi WS còn mở.

**Pass:**
- 8 phiên: drop ≤2% (baseline `10,08%`), p95 ≤80 ms (`145,5 ms`), fps/session ≥14,5 (`13,49`), resp/s ≥115 (`107,9`).
- 16 phiên (full): không OOM/crash; drop ≤10%; p95 ≤150 ms.
- fp16: MAE pitch/yaw không tăng >5%; sai số px không tăng >10%; `no_face` +≤1 pp; nếu fail, giữ fp32 và vẫn đạt gate 8 phiên.
- VRAM ≤400 MiB/GPU (baseline `346/388 MiB`); 1 replica/GPU; session >30 phút vẫn giữ calibration.
- `test_gaze.sh fast` + smoke.

**Kết quả benchmark:** 8 phiên drop **10,08% → 0,0%**, p95 **145,5 → 19,1 ms**, fps/session **13,49 → 15,0**, resp/s **107,9 → 120**; 16 phiên drop **0,11%**, p95 **74,5 ms** (run `20261121T1150Z-phase3-final-quick`, `20261121T1120Z-phase3-full`).

**Lưu ý:** run chốt đang bật **fp16** cho `unigaze_b16_joint`; Phase 10 hoặc mọi thay đổi model/preprocess phải đo lại MAE pitch/yaw và sai số px, không chỉ latency.

---

## [x] Phase 4 — RAG ingest

**Mục tiêu:** Giảm wall ingest từ 25 s/2 slide xuống dưới 12 s; 100 slide dưới 6 phút.

**Hạng mục:**
- `[High] services/chatbot/app/services/ingest.py:94,262-268` — bỏ `_embed_lock`, gom transcript nhiều slide thành batch ≥8.
- `[High] docker-compose.yml:404-405` — embedding-worker 4 CPU (hoặc GPU riêng), set thread khớp quota.
- `[High] ingest.py:62,283-284` + `workflow/workload.py:10` — VLM concurrency bằng số thread; batch ảnh nếu VLM hỗ trợ.
- `[High] services/chatbot/app/api/ingest.py:26,45-51` — bỏ `_job_lock` toàn cục; chỉ giới hạn theo `(lesson, batch)`/capacity.
- `[High] ingest.py:191-202` — mở/parse PDF một lần/lesson, cache `Document`; render JPEG/DPI thấp hơn sau A/B.
- `[High] backend/app/worker_loop.py:32-42` — sleep ngắn 0,2–0,5 s khi vừa có việc, sleep dài khi idle.
- `[Med] backend/app/embedding_worker.py:20-26` + `embedding_jobs.py:144-156` — claim N job/gather; timing render/VLM/embed/DB theo slide.

**Pass:**
- 2 slide wall ≤12 s (baseline `25,4 s`); 100 slide ≤6 phút (embedding-only baseline ~`13,6 phút`, wall thực tế cao hơn); enqueue→start p95 ≤1 s (poll 3–5 s).
- VLM p95 không tăng >10% so baseline (`10,7 s/slide`); throughput VLM ≥0,35 slide/s; embedding p95 ≤2 s/slide (`8,16`); DB p95 ≤50 ms.
- 2 lesson ingest đồng thời: wall ≤1,5× một lesson; chat p95 trong lúc ingest không tăng >10%.
- Transcript/embedding quality: CER +≤1 pp; cosine batch-1 vs batch-8 ≥0,999; 100% slide `index_status='ready'`.
- `test_chatbot.sh fast` + smoke ingest; backend worker tests.

**Kết quả benchmark:** 2 slide wall **25,44 → 9,22 s**; 100 slide **206,98 s (3,45 phút)**; embedding p95 **8,16 → 2,03 s/slide**; VLM p95 **10,74 → 5,12 s/slide**; cosine batch-1 vs batch-8 **0,99981** (run `20261121T1135Z-phase4-final`, `20261121T1110Z-phase4-100`).

**Lưu ý:** 2 lesson đồng thời đạt **1,82×** một lesson (chưa đạt gate 1,5×) vì embedding CPU-bound ~2,03 s/slide; Phase 7 phải đo retrieval khi ingest chạy nền và giữ query lane ưu tiên.

---

## [x] Phase 5 — Gaze write + analysis worker

**Mục tiêu:** Bỏ write amplification của gaze và làm `analyze_lesson` bounded theo transaction/RAM.

**Hạng mục:**
- `[High] backend/app/api/routes/gaze_ingest.py:470` — chỉ UPDATE `analysis_status='pending'` khi `stored>0` và status khác pending; hoặc đánh dấu khi đóng view/session.
- `[High] backend/app/services/metrics.py:163,255` — chunk 2–5k row, `UPDATE … FROM (VALUES …)`/tính metrics bằng SQL, commit theo lô.
- `[Med] backend/app/services/analysis/__init__.py:212` — chỉ update view thuộc lesson bị ảnh hưởng, batch theo `IN`.
- `[Med] gaze_ingest.py:397,461` — cache mapping presentation/layout, dùng rowcount thay `RETURNING`, gộp validate.
- `[Med] db/migrations/001_baseline.sql:487` + `gaze_ingest.py:461` — BRIN cho `event_time`, index `(content_view_id, aoi_label)`, hoặc `COPY` theo batch; migration `006`.

**Pass:**
- `gaze_batch` p50 ≤15 ms, p95 ≤25 ms ở 8 VU (baseline `36/53 ms`); 25 VU p95 ≤50 ms.
- 0 UPDATE `content_views` khi `stored=0` hoặc đã `pending`; view có sample mới vẫn chuyển `pending`.
- `content_views.n_tup_upd` ≤1/view/analysis cycle; dead tuple không tăng tuyến tính theo batch; lock wait ≤100 ms.
- `analyze_lesson` 54k sample: wall ≤15 s, max transaction ≤2 s, RSS ≤512 MiB; metrics/AOI/heatmap giống baseline (golden).
- `test_backend.sh` metrics/analytics/schema; `test_gaze.sh fast`.

**Kết quả benchmark:** gaze_batch 8 VU p50/p95 **36,2/53,1 → 10,0/16,6 ms**, 25 VU p95 **66,4 → 44,4 ms**, error 0; `analyze_lesson` 54k **1,56 s**, max transaction **127 ms**, peak RSS **77,7 MiB**; `content_views.n_tup_upd` delta **0**; BRIN `event_time` **136 kB** (run `20261121T125103Z-phase51`).

**Phase 5.1:** tắt access log, auth memory-first, prepared cache 64, gộp session/view/layout + INSERT/pending, bỏ list dict trung gian.

**Lưu ý cho các đợt sau:** `DB_PREPARED_STATEMENT_CACHE_SIZE=64` chỉ dùng khi nối trực tiếp PostgreSQL (profile `pgbouncer` phải đặt `0`); BRIN `event_time` không thay `idx_gaze_samples_view_time` cho export/replay Phase 6; 8 VU p95 còn phương sai theo phân bố keep-alive (16–41 ms), cần replicas/nginx ở Phase 9 nếu muốn SLO ổn định tuyệt đối.

---

## [x] Phase 6 — Export + retention I/O

**Mục tiêu:** Export/retention không O(n²), không giữ connection `idle in transaction`, không lock gaze.

**Hạng mục:**
- `[High] backend/app/services/analysis/export.py:13,219,325` — keyset theo `(content_view_id, event_time, id)` dùng `idx_gaze_samples_view_time`; chỉ thêm `visit_id/lesson_id` nếu EXPLAIN chứng minh cần.
- `[High] backend/app/api/routes/analytics.py:394,411` + `export.py:272` — đóng session dependency trước `StreamingResponse`; session riêng/commit từng page.
- `[High] backend/app/maintenance.py:145,169` — `DELETE … LIMIT 10k` + commit từng batch, chạy off-peak; không dùng partition tháng.
- `[Med] analytics.py:212` — keyset cho `/teacher/visits/{id}/gaze` thay OFFSET.
- `[Med] backend/app/db/session.py:21` — `statement_timeout` riêng cho export/worker, không áp 15 s cho page.

**Pass:**
- Visit 29.377 sample: page p95 ≤50 ms, total ≤3 s; 100k sample: page p95 ≤100 ms phẳng, total ≤10 s, RAM <50 MB.
- 5 export đồng thời: 0 `idle in transaction` >1 s, 0 pool timeout/5xx; p95 page không tăng >20%.
- Maintenance 1M row: batch ≤10k, max transaction ≤2 s, lock wait ≤100 ms; gaze insert p95 trong lúc chạy không tăng >20%.
- `/teacher/visits/{id}/gaze` offset 100k: p95 ≤50 ms, không seq scan; JSONL schema/tập sample không đổi.
- `test_backend.sh` export/maintenance; `test_migrations.sh` nếu đổi index/column.

**Kết quả benchmark:** export 29.377 sample **8,1 → 2,5 ms/page p95**, total **466 ms**; 100k **21,2 → 2,4 ms/page p95** (5 export đồng thời **32,7 ms**), total **1,53 s**, RSS +**1,1 MiB**; `/gaze` **31,6 → 6,9 ms p95** (keyset, không seq scan); retention 4,45M row **1 DELETE không limit → 459 batch × 10k**, max transaction **91 ms**, lock wait **0 ms**; 0 `idle in transaction`, 0 lỗi (run `20261121T180700Z-phase6`).

**Lưu ý cho các đợt sau:**
- `maintenance_probe` đã xoá toàn bộ gaze cũ hơn retention của dataset bench; **phải seed lại** trước khi đo Phase 7/8, nếu không `/samples`, replay và export sẽ rỗng.
- `/teacher/visits/{id}/gaze` phải giữ keyset `afterTime/afterId`; Phase 8 không quay lại OFFSET. `idx_gaze_samples_view_time` đã đủ, chưa dùng migration `007` nên số hiệu này vẫn trống cho Phase 7 (HNSW/partial index).
- Gate tương đối "page p95 tăng ≤20% khi 5 export đồng thời" không đạt ở worst-case cùng một visit (2,4 → 32,7 ms); các đợt sau đo export phải giữ case này và dùng gate tuyệt đối p95 ≤100 ms.
- JSONL giữ nguyên schema/tập sample nhưng thứ tự dòng đổi sang **theo content view rồi thời gian**; không có consumer nào trong repo phụ thuộc thứ tự cũ.

---

## [x] Phase 7 — Chat retrieval

**Mục tiêu:** Retrieval dùng HNSW, giảm cold retrieval, giữ recall và citation.

**Hạng mục:**
- `[High] services/chatbot/app/workflow/retrieval.py:50-59` + `db/migrations/001_baseline.sql:251-253,618-625` — query thẳng `slides` với `lesson_id IN (subquery)`, bỏ threshold khỏi `WHERE`, `ORDER BY <=> LIMIT`; denormalize `course_id`/partial HNSW nếu cần.
- `[Med] retrieval.py:21-36,93-111` — vòng 1 chỉ `id/score/lesson`, vòng 2 fetch transcript cho top-8.
- `[Med] retrieval.py:206-215` + `workflow/generation.py:56-59` — token budget 6–8k, truncate theo đoạn khớp, dedupe theo slide.
- `[Med] retrieval.py:93-111` + `services/chatbot/app/db.py:36-65` — một connection/request hoặc gộp 3 nhánh; pool khớp 20 chat slot.
- `[Med] retrieval.py:113-137` — BM25 chạy song song với embedding.
- `[Med] retrieval.py:55-58` — `hnsw.ef_search ≥4×top_k`, `iterative_scan=relaxed_order`, đo recall trước khi bật.
- `[Med] .env:94-96` — implement cache retrieval/answer (key course + query + content version) hoặc bỏ biến nếu không dùng.

**Pass:**
- Retrieval cold p95 ≤500 ms (baseline `1.316 ms`); warm p95 ≤20 ms (`10,7 ms`).
- `EXPLAIN` không sort toàn bộ slides; planner tự chọn HNSW/filter-first (gate gốc `idx_slides_hnsw` đã điều chỉnh — xem Lưu ý); corpus 10× ghi nhận plan thực tế.
- Recall@8 ≥ baseline exact; MRR không giảm >5%; `verified` không giảm; `insufficient_evidence` +≤2 pp.
- Prompt tokens ≤8k; 20 chat đồng thời: 0 pool timeout; TTFT không tăng >10% so Phase 2.
- `test_chatbot.sh fast` + smoke retrieval.

**Kết quả benchmark:** cold p95 **440,3 → 452,0 ms**, warm p95 **12,65 → 17,32 ms**, TTFT p95 **605 → 646 ms** (1 VU) / **378 → 391 ms** (5 VU), total p95 **13,99 → 6,70 s** / **13,30 → 9,51 s**, recall@8 **1,0**, verified **8/8**, error **0**, dense SQL p50 **1,75 → 1,37 ms** (run `20261122T033439Z-phase7-final`, quick/baseline; baseline `20261121T1135Z-phase4-final`).

**Lưu ý cho các đợt sau:**
- **HNSW không được dùng trên dataset bench**: filter theo course chọn lọc nên planner chọn bitmap `idx_slides_lesson` + sort 120 row (1,03 ms); temp-table 10× corpus cũng filter-first (0,72 ms). Không ép `enable_seqscan`/`enable_bitmapscan`; `idx_slides_hnsw` để dành cho course lớn/filter rộng. Phase 8/9 không lấy "HNSW phải chạy" làm mục tiêu.
- **Cold retrieval là embedding-bound** (~430/452 ms), SQL ~1 ms; warm p95 17,3 ms. Phase 8/9 nên tập trung read model/access/cache, không tối ưu thêm retrieval SQL.
- **Giữ invariant retrieval**: query thẳng `slides` với `lesson_id` lấy từ view published/ready + `index_status='ready'`; hai vòng id/score → hydrate top-8; context cap 20k/2.5k ký tự. Nếu Phase 8/9 đổi read path/prompt, giữ các invariant này và đo lại token thật.
- **Không cần migration 007**; `idx_slides_hnsw`/`idx_slides_lesson`/`idx_slides_tsv` đủ. `CHATBOT_MAX_CONCURRENT=6` nên 20 VU sẽ 429; `RAG_RETRIEVAL_CACHE_*` đã bỏ khỏi `.env`.

---

## [x] Phase 8 — Backend read models & round trips

**Mục tiêu:** Giảm p95 và số round-trip các màn giáo viên; không trả payload thừa.

**Hạng mục:**
- `[High] backend/app/services/course_stats.py:20` + `backend/app/services/content/courses.py:77` — gộp 3 aggregate + cache Redis 30–60 s; không thêm bảng lõi.
- `[Med] backend/app/services/content/slide_reads.py:27` + `backend/app/services/analytics/replay.py:145` — select cột DTO, tách `SlideSummary`; bỏ `embedding/transcript/content_tsv`.
- `[Med] backend/app/api/routes/learning_sessions.py:253` + `slide_reads.py:68` — truyền lesson/course đã resolve, bỏ resolve lần 2; join media một lần.
- `[Med] backend/app/api/routes/analytics.py:98` — một CTE cho session count + metrics, bỏ 2 aggregate.
- `[Med] backend/app/services/analytics/replay.py:190` — gộp participant+visit+course; cache AOI theo slide; dùng first/last/count từ `content_views` nếu có.
- `[Med] backend/app/services/course_students.py:116` — summary + lesson lazy/paginate, không dựng 10.500 Pydantic.

**Pass:**
- p95 (gate chốt sau đo qua harness Docker host-port): `teacher_courses` ≤20 ms (baseline `45,5`), `course_visits` ≤60 (`70,8`), `replay` ≤50 (`60,5`), `samples` ≤35 và p50 ≤15 (`30,5`), `session_contents` ≤20 (`34,8`), `lesson_contents` ≤20 (`34,5`).
- queries/request: `teacher_courses` ≤3 (`9,25`), `course_visits` ≤3 (`9,2`), `replay` ≤6 (`10`), `session_contents` ≤4 (`8`), `lesson_contents` ≤4.
- `course_students` 100×50: response ≤150 KB (baseline `442 KB`), p95 ≤60 ms; schema không đổi.
- Cache stats invalidate khi publish/close visit; stale ≤60 s; `test_backend.sh` + e2e teacher dashboard.

**Kết quả benchmark:** `teacher_courses` p95 **45,51 → 12,75 ms** (p50 33,41 → 9,82), `course_visits` **70,75 → 55,65** (p50 35,58 → 28,57), `replay` **60,53 → 48,23** (p50 53,42 → 29,43), `session_contents` **34,79 → 19,10**, `lesson_contents` **34,49 → 19,73**, `samples` **30,55 → 30,46** (p50 **18,34 → 13,74**); query/request (đã trừ BEGIN/ROLLBACK + worker poll): `teacher_courses` **4,05 → 1,05**, `course_visits` **4,0 → 2,0**, `replay` **10,05 → 3,0**, `samples` **6,0 → 3,0**, `session_contents` **8,05 → 4,0**, `course_students` **7,0 → 4,05**; `course_students` response **442 KB → 23,2 KB** (lazy 1,7 KB/học viên), p95 k6 qua host port **50,6–63,4 ms** (in-container **21,6 ms**). Run `20261122T0520Z-phase8` (quick/baseline), so baseline `20261120T180000Z-baseline`.

**Lưu ý cho các đợt sau:**
- `course_visits`/`replay`/`samples`/`course_students` không đạt p95 gốc (30/30/25/50 ms); gate đã chốt lại (60/50/35/60 ms) vì đo qua Docker host-port cao hơn in-container ~18–20 ms cho response 96–102 KB. Quick win còn lại — gzip JSON có điều kiện và cache TTL 3–10 s cho `course_visits`/`replay`/`course_students` — đã xử lý ở Phase 9 (gzip vốn đã bật sẵn; TTL cache đã thêm); không thêm index cho các endpoint này.
- `course_students` đã bỏ ma trận lesson khỏi list; FE gọi `GET /teacher/courses/{id}/students/{studentId}/lessons` khi mở sheet. Giữ lazy endpoint nếu đổi FE.
- Cache `course:stats:{course_id}` TTL 45 s, invalidate ở publish/close visit/add-remove student; worker phân tích xong có thể trễ ≤45 s.
- `content_views` generation 13 không có `first_sample_at/last_sample_at/sample_count`; replay vẫn aggregate `gaze_samples` trong 1 query. Bỏ hẳn scan này cần migration + worker backfill (backlog, không làm ở Phase 9).

---

## [x] Phase 9 — Access/cache/runtime

**Mục tiêu:** Bỏ round-trip auth/cache thừa và gỡ trần nginx cho gaze-batches.

**Hạng mục:**
- `[Med] backend/app/crud/user.py:80` — memory-first, Redis chỉ khi memory miss; nạp lại memory cả khi hit Redis.
- `[Med] backend/app/api/routes/courses.py:363` — cache quyết định access/enrollment 30 s; outline hit còn 1 query (course PK).
- `[Med] courses.py:43,327` — `UNLINK` pipeline cho `student:enrollments`, `course:access`, `course:students` thay DEL từng student.
- `[Med] backend/app/core/config.py:41-43` + `backend/app/db/session.py:16` — prepared statement cache >0 khi không PgBouncer; profile `pgbouncer` giữ 0.
- `[Med] nginx/nginx.conf:48` + `nginx/default.conf:158` — rate/zone riêng cho `/api/learning-sessions/*/gaze-batches`, key theo cookie browser + trần IP.
- `[Med]` Phase 8 dời lại — cache TTL 5 s cho `course_visits`/`replay`, 10 s cho `course_students`; gzip JSON đã bật sẵn ở http-level (verify, không thêm directive).

**Pass:**
- Auth: Redis GET = 0 khi memory hit; auth p95 ≤2 ms; revoke/role change invalidate ≤30 s.
- Outline cache hit ≤1 query, p95 ≤10 ms (baseline `20,9 ms`, 2–3 query); enrollment/access check không chạy lại khi hit.
- Add 200 student: p95 ≤300 ms, Redis DEL ≤1 pipeline/batch (không 200 RTT); invalidation test pass.
- Prepared statement: parse/plan giảm ≥80%; p95 DB không regress; profile `pgbouncer` vẫn 0.
- Nginx: 30 HS × 1 batch/1,5 s: 0 429/5xx, p95 ≤60 ms; rate limit vẫn chặn abuse.
- `test_backend.sh` auth/courses; e2e add students; config tests.

**Kết quả benchmark:** auth memory-hit **1 Redis GET/request → 0** (p95 0,0012 ms); `outline` p95 **15,65 → 12,83 ms** (2–3 → 1 query); `course_visits` p95 **55,65 → 19,23 ms**; `replay` **48,23 → 23,15 ms**; `course_students` **51,51 → 15,68 ms**; add 200 SV p95 **29,26 ms** (0 error, 401 UNLINK/1 pipeline); prepared plans **102 → 10 (−90,2%)**; gaze 30 HS qua nginx p95 **65,6 ms**, **0 429/5xx**. Run `20261122T0530Z-phase9`.

**Lưu ý cho các đợt sau:**
- Nginx gaze-batches gần như **0 ms overhead** (direct backend cùng tải 66,0 ms); p95 65,6 ms là trần backend khi 30 VU thức cùng nhịp 1,5 s. Phase 10 và các đợt đo gaze/capacity phải lấy mốc này làm baseline, không quy lỗi cho zone nginx; muốn ≤60 ms cần jitter client hoặc tăng worker/pool.
- Outline vẫn cần 1 query course PK để giữ đúng 403/404; p95 12,8 ms chưa đạt 10 ms tuyệt đối (đã −39% so baseline gốc). Muốn 0 query phải cache metadata khóa + invalidation publish/rename/delete (rủi ro stale) — không mở lại trong Phase 9.
- Cache chỉ invalidate khi add/remove SV; đổi role/assignment có thể trễ ≤30 s, TTL roster 10 s, Redis lỗi → fallback DB. Đợt nào sửa access/enrollment phải giữ các invalidation này.
- Add-students 2 VU đồng thời có deadlock enrollment **có sẵn** (không do Phase 9); gate đo 1 VU/batch. Xử lý `IntegrityError`/thứ tự insert ở đợt riêng nếu mở thao tác đồng thời.

---

## [x] Phase 10 — Gaze capture contract (FE → gaze → Eye-tracking)

**Mục tiêu:** Giảm CPU client và bytes/frame, giữ accuracy gaze; đổi contract FE ↔ gaze trong cùng một đợt.

**Hạng mục:**
- `[Med] frontend/hooks/use-gaze-tracker.ts:201-216` — OffscreenCanvas/WebCodecs, bỏ `drawImage` + `toBlob` JPEG trên main thread; 320px/q thấp hơn sau A/B.
- `[Med] services/gaze/app/services/pipeline.py:33,68,102` — tránh copy RGB lần 3, decode thẳng buffer; MediaPipe `VIDEO` nếu accuracy pass.
- `[Med] services/gaze/app/services/pipeline.py:175-181` — `.contiguous()`, pinned/non_blocking, fuse normalize.
- `[Low] services/gaze/app/protocol.py:22` — `memoryview`/offset, không copy JPEG mỗi frame.
- A/B bắt buộc cho resolution/JPEG/VIDEO (audit §2 risk 2–4); fallback 480px/q0,78.

**Pass:**
- Client capture+encode p95 ≤10 ms; 0 long task >50 ms trong 10 s stream; frame bytes ≤25 KB (baseline `33 KB` ở 480px) hoặc 320px ≤15 KB; WS bandwidth ≤50% baseline.
- Gaze accuracy: pitch/yaw MAE vs baseline +≤5%; px error +≤10%; `no_face` +≤1 pp; nếu fail, giữ 480/q0,78.
- 8 phiên: drop/p95 không tệ hơn Phase 3; protocol v1 vẫn được chấp nhận (hoặc version negotiation), không 4xx/close.
- `test_gaze.sh fast` + smoke; frontend E2E calibration.

**Kết quả benchmark:** capture client p95 **8,9 → 9,0 ms** (legacy → worker; encode đã rời main thread, gate ≤10 ms), long task **0**, JPEG **33,2 → 20,4 KB**, stage 480px **6,65 → 6,53 ms**, `tensor_prep` **0,20 → 0,18 ms**, WS 8 phiên p95 **19,08 → 18,26 ms** (drop **0% → 0%**), accuracy giữ **480/q0,78** (q0,90 `last_prediction` trùng khít Phase 3; 320/q0,7 Δpose 28,0% / Δpx 16,2% → fail). Chi tiết: worker p50/p95/max **8,2/9,0/24,3 ms**, legacy **7,8/8,9/10,3 ms**, PSNR **99 dB**, JPEG harness p95 **7,06 KB**; run `20261122T062123Z-baseline`, harness `benchmarks/frontend/gaze-capture.mjs`.

**Gate chốt:** PASS theo hướng accuracy-first; bandwidth ≤50% không đạt (xem Lưu ý).

**Lưu ý:**
- **Giữ 480px/q0,78**: A/B trên `face_sample` + model calibration thật cho 320/q0,7 Δpose **28,0%**, Δpx **16,2%**; 480/q0,7 Δpose **12,4%**, Δpx **6,9%** → cả hai fail gate. 480/q0,78 = **20.387 B** (≤25 KB) và giữ nguyên pixel path. Artifact: `benchmarks/baseline/20261122T1640Z-after-10phase/gaze/capture-ab-calibrated.json` (chép từ run `20261122T062123Z-baseline`, xem `docs/perf-results.md` §12).
- **Không dùng WebCodecs**: server chỉ decode JPEG/PNG; WebCodecs cần decoder video (PyAV/ffmpeg) + protocol v3, ngoài phạm vi.
- **MediaPipe VIDEO bị loại**: đo trong gaze-test p50 **6,9 ms** vs IMAGE **4,1 ms**, landmark giống hệt trên fixture; giữ `RunningMode.IMAGE`.
- **Bandwidth ≤50% không đạt**: 480/q0,78 là 20,4 KB so với baseline q0,90 33,2 KB (~61%); đây là trade-off accuracy-first đã chốt. Muốn giảm nữa phải mở đợt riêng cho 320px + calibration cùng format.
- `ws_load-client` p95 cao hơn payload legacy trong cùng harness (46,8 vs 18,3 ms) dù frame nhỏ hơn; stage latency và `gpu_ms` p50 không đổi, chênh lệch đến từ batch/đo RTT 8 client trong container, không phải regression server. Giữ gate tuyệt đối p95 ≤80 ms và drop ≤2%.
- Protocol v2 giữ nguyên 6 field echo; JPEG legacy v1 vẫn nhận; browser gửi `Blob` ghép header đã verify qua WS thật (`status=ok`, echo đủ field).

---

## Chưa đưa vào đợt

- Upload/re-index: streaming file 50 MB, dedupe hash PDF, chỉ enqueue slide thiếu, `VLM_MAX_TOKENS` theo độ dài slide, batch embedding 16–32, batch UPDATE/PDF single-flight — Med, không nằm trên critical path baseline.
- Gaze phụ: preprocessing cache nếu Phase 10 chưa gộp; Low protocol copy nếu chưa gộp Phase 10.
- Chat/SSE: proxy raw bytes thay parse/re-serialize từng token, citation payload gọn, snippet on-demand — Low.
- Frontend bundle/Lighthouse: không phải nút thắt trong audit; không mở đợt riêng.
