# Cleanup status

## Baseline

- Branch: `cleanup/base`
- Commit: `7e4c77a`
- Date: 2026-11-09

### Static checks

| Check | Result |
|---|---|
| ruff | pass |
| eslint | pass |
| tsc | pass |
| knip | pass |
| pytest | 76 passed (final) |
| frontend unit tests | 222 passed (final) |
| frontend build | pass |
| smoke | pass |
| migrations | pass (2 migrations, schema generation 7) |

### Metrics

| Metric | Baseline | Target | After |
|---|---|---|---|
| Gaze batch queries | 14 (P4 baseline) | ≤ 5 | 9 (P1) |
| Teacher course list queries | 6 (P4 baseline) | ≤ 10 | 6 |
| Course students queries | 9 (P4 baseline) | ≤ 10 | 9 |
| Media asset queries | 17 (P4 baseline) | ≤ 5 | 4 (P2) |
| Client JS chunks total | 2,516.0 KB (57 chunks, webpack analyze) | ≤ baseline | 2,556.7 KB (59 chunks, webpack analyze; +1.6%, within 5% budget) |
| Initial JS `/` | 705.5 KB | ≤ baseline, tốt nhất −10% | 692.4 KB (−1.9%) |
| Landing page chunk | 19,276 B | giảm | 5,986 B (−69%) |
| Initial JS `/student` | not measured | ≤ baseline | build pass; follow-up measure |
| Initial JS `/teacher` | not measured | ≤ baseline | build pass; follow-up measure |

## Waves

| Wave | Status | Tag | Notes |
|---|---|---|---|
| 0 | done | | Foundation |
| 1 | done | `cleanup/wave-1` | Quick wins + test infra (A1–A4 merged) |
| 2 | done | | Backend split B1–B4 merged |
| 3 | done | | ORM performance P1–P4 merged |
| 4 | done | | Frontend split F1–F5 merged |
| 5 | done | | Scale readiness S1–S3 merged |
| 6 | done | `cleanup/done` | Final integration + full gate |

## Final gate

```bash
./scripts/check.sh --full   # ruff, lint, typecheck, knip, 222 FE tests, 81 BE tests, build
./scripts/test_migrations.sh # 2 migrations, schema_generation=7
./scripts/smoke.sh           # nginx/backend/gaze/chatbot OK
docker compose up -d --build # stack rebuilt, embedding-worker running
```

## Concurrency hardening (2026-11-09)

- Chat SSE không còn giữ DB connection trong lúc stream; 10 stream đồng thời
  giữ `db_pool.checked_out = 0`.
- Backend chạy 2 uvicorn worker; pool mỗi process 4–10; pool timeout 5s trả 503.
- Postgres: `shared_buffers=1GB`, `effective_cache_size=3GB`, 4 CPU/4GB.
- Redis cache auth 30s + enrollments 30s + course outline 60s.
- Nginx: 2 worker, rate limit, connection limit, upstream `max_conns`,
  `X-Accel-Redirect` cho media local.
- Frontend: 2 replica sau nginx.
- Gaze: 2 replica + `ip_hash`, queue limit 32 + throttle 80ms/frame; overload
  trả 503/overloaded.
- Chatbot: giới hạn `CHATBOT_MAX_CONCURRENT`, quá tải trả 429.
- Analysis worker: 2 replica; maintenance tạo/drop partition gaze theo
  `GAZE_RETENTION_DAYS`.
- PgBouncer tùy chọn sau profile `pgbouncer`; `DB_PREPARED_STATEMENT_CACHE_SIZE=0`.
- Thêm `GET /internal/metrics`, `scripts/loadtest.sh`, `loadtest/browse.js`.
- Chi tiết: `docs/performance/CONCURRENCY.md`.

## Follow-ups

- Gaze batch còn 9 query (mục tiêu ≤ 5); phần còn lại là auth + insert + query bắt buộc.
  Có thể gộp auth/enrollment lookup hoặc cache session ngắn hạn nếu cần.
- Chưa đo riêng initial JS `/student` và `/teacher`; nên thêm script đo theo route.
- Embedding job queue chưa có stale-running recovery; thêm lease/timeout nếu chạy nhiều worker.
- Chưa có Playwright E2E; nên bổ sung 5 flow chính ở wave sau.
- Có thể generate TypeScript types từ OpenAPI để giảm drift frontend/backend.
- Cân nhắc chuyển dần ORM default sang `lazy="raise"` sau khi query-count tests đã phủ rộng.
