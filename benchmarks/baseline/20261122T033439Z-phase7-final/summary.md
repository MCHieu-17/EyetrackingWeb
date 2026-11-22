# Benchmark summary — 20261122T033439Z-phase7-final

## Dataset

| Table | Rows |
|---|---:|
| users | 202 |
| courses | 6 |
| course_modules | 21 |
| lessons | 105 |
| slides | 540 |
| aois | 243 |
| enrollments | 400 |
| course_visits | 419 |
| learning_sessions | 1,057 |
| content_views | 19,240 |
| view_layouts | 160 |
| gaze_samples | 3,445,200 |
| chat_sessions | 200 |
| chat_messages | 2,000 |
| quiz_attempts | 1,000 |
| gaze_calibrations | 100 |
| background_jobs | 100 |

## Chatbot

### Query trực tiếp

| concurrency | rps | ttft_p95 | total_p95 | error |
|---|---|---|---|---|
| 1 | 0.191 | 645.89 | 6704.94 | 0.0 |
| 5 | 0.503 | 391.11 | 9511.08 | 0.0 |

### Ingest

- slides: 2 / processed: 2 / wall: 6530.87 ms

| stage | p50 | p95 | mean |
|---|---|---|---|
| pdf_render | 48.93 | 48.93 | 39.45 |
| vlm | 2434.14 | 2434.14 | 2402.38 |
| embedding | 2026.99 | 2026.99 | 2026.99 |
| db_upsert | 3.08 | 3.08 | 2.83 |
| db_mark | None | None | None |

## Redis

- hit rate before: None
- hit rate after: None
