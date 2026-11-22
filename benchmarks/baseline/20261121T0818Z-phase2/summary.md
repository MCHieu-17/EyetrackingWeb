# Benchmark summary — 20261121T0818Z-phase2

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
| 1 | 0.171 | 1771.28 | 7757.43 | 0.0 |
| 5 | 0.689 | 336.22 | 8809.72 | 0.0 |

### Ingest

- slides: 2 / processed: 2 / wall: 16227.83 ms

| stage | p50 | p95 | mean |
|---|---|---|---|
| pdf_render | 56.55 | 56.55 | 53.12 |
| vlm | 2294.57 | 2294.57 | 2271.03 |
| embedding | 7469.54 | 7469.54 | 6958.29 |
| db_upsert | 14.74 | 14.74 | 8.97 |
| db_mark | 8.08 | 8.08 | 4.75 |
