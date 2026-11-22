# Benchmark summary — 20261121T1110Z-phase4-100

## Dataset

| Table | Rows |
|---|---:|
| users | 202 |
| courses | 6 |
| course_modules | 21 |
| lessons | 105 |
| slides | 620 |
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
| 1 | 0.175 | 1688.15 | 6826.21 | 0.0 |
| 5 | 0.581 | 704.21 | 11279.26 | 0.0 |

### Ingest

- slides: 100 / processed: 100 / wall: 206977.27 ms

| stage | p50 | p95 | mean |
|---|---|---|---|
| pdf_render | 26.4 | 51.36 | 29.92 |
| vlm | 3878.26 | 5404.93 | 4022.44 |
| embedding | 2028.11 | 2082.07 | 2028.28 |
| db_upsert | 1.52 | 2.81 | 1.74 |
| db_mark | None | None | None |
