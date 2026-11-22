# Benchmark summary — 20261121T1106Z-phase4

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
| 1 | 0.194 | 789.83 | 6694.3 | 0.0 |
| 5 | 0.639 | 337.39 | 9998.99 | 0.0 |

### Ingest

- slides: 2 / processed: 2 / wall: 7293.99 ms

| stage | p50 | p95 | mean |
|---|---|---|---|
| pdf_render | 30.1 | 30.1 | 27.19 |
| vlm | 3204.61 | 3204.61 | 3186.39 |
| embedding | 2012.76 | 2012.76 | 2012.76 |
| db_upsert | 21.24 | 21.24 | 14.14 |
| db_mark | None | None | None |
