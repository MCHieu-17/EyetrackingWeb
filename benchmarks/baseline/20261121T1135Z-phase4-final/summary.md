# Benchmark summary — 20261121T1135Z-phase4-final

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
| 1 | 0.104 | 605.26 | 13991.92 | 0.0 |
| 5 | 0.427 | 378.42 | 13302.39 | 0.0 |

### Ingest

- slides: 2 / processed: 2 / wall: 9215.9 ms

| stage | p50 | p95 | mean |
|---|---|---|---|
| pdf_render | 29.15 | 29.15 | 27.15 |
| vlm | 5120.21 | 5120.21 | 5033.52 |
| embedding | 2028.54 | 2028.54 | 2028.54 |
| db_upsert | 2.45 | 2.45 | 2.43 |
| db_mark | None | None | None |
