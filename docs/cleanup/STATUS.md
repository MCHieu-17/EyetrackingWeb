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
| pytest | 84 passed (final) |
| frontend unit tests | 224 passed (final) |
| Playwright E2E | 4 passed |
| frontend build | pass |
| smoke | pass |
| migrations | pass (2 migrations, schema generation 7) |

### Metrics

| Metric | Baseline | Target | After |
|---|---|---|---|
| Gaze batch queries | 14 (P4 baseline) | ≤ 5 | 5 (auth cache + join) |
| Teacher course list queries | 6 (P4 baseline) | ≤ 10 | 6 |
| Course students queries | 9 (P4 baseline) | ≤ 10 | 9 |
| Media asset queries | 17 (P4 baseline) | ≤ 5 | 4 (P2) |
| Client JS chunks total | 2,516.0 KB (57 chunks, webpack analyze) | ≤ baseline | 2,556.7 KB (59 chunks, webpack analyze; +1.6%, within 5% budget) |
| Initial JS `/` | 705.5 KB (webpack) | ≤ baseline, tốt nhất −10% | 692.4 KB (webpack, −1.9%); 169.7 KB (Turbopack manifest) |
| Landing page chunk | 19,276 B | giảm | 5,986 B (−69%) |
| Initial JS `/student` | not measured | ≤ baseline | 299.1 KB (Turbopack manifest) |
| Initial JS `/teacher` | not measured | ≤ baseline | 283.8 KB (Turbopack manifest) |

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
./scripts/check.sh --full   # ruff, lint, typecheck, knip, 224 FE tests, 84 BE tests, build
./scripts/e2e.sh            # 4 Playwright smoke flows
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
- Gaze: 2 replica + cookie affinity, queue limit 32 + throttle 80ms/frame;
  overload trả 503/overloaded.
- Chatbot: giới hạn `CHATBOT_MAX_CONCURRENT`, quá tải trả 429.
- Analysis worker: 2 replica; maintenance tạo/drop partition gaze theo
  `GAZE_RETENTION_DAYS`.
- PgBouncer tùy chọn sau profile `pgbouncer`; `DB_PREPARED_STATEMENT_CACHE_SIZE=0`.
- Thêm `GET /internal/metrics`, `scripts/loadtest.sh`, `loadtest/browse.js`.
- Chi tiết: `docs/performance/CONCURRENCY.md`.

## Follow-ups

- Gaze batch đã đạt 5 query (từ 14 baseline) nhờ auth cache + gộp query.
- Initial JS theo route đo bằng `node scripts/bundle-report.mjs` (Turbopack).
- Embedding job queue chưa có stale-running recovery; thêm lease/timeout nếu chạy nhiều worker.
- Playwright E2E smoke đã có (`./scripts/e2e.sh`, 4 flow: landing/student/teacher/admin).
- Có thể generate TypeScript types từ OpenAPI để giảm drift frontend/backend.
- Cân nhắc chuyển dần ORM default sang `lazy="raise"` sau khi query-count tests đã phủ rộng.
