# Benchmark summary — 20261122T032544Z-phase7

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
| 1 | 0.187 | 604.01 | 7961.44 | 0.0 |
| 5 | 0.636 | 344.92 | 9178.28 | 0.0 |

### Ingest

- slides: 2 / processed: 2 / wall: 7420.6 ms

| stage | p50 | p95 | mean |
|---|---|---|---|
| pdf_render | 30.38 | 30.38 | 28.83 |
| vlm | 3274.1 | 3274.1 | 3259.81 |
| embedding | 2052.76 | 2052.76 | 2052.76 |
| db_upsert | 2.93 | 2.93 | 2.74 |
| db_mark | None | None | None |

## Redis

- hit rate before: None
- hit rate after: None
