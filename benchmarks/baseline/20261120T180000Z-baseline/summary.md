# Benchmark summary — 20261120T180000Z-baseline

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

## Backend (k6)

| scenario | p50 | p95 | p99 | rps | error_rate | count |
|---|---|---|---|---|---|---|
| aoi_summary | 1249.2489460000002 | 1307.93029815 | 1316.13079643 | 1.378679860808355 | 0 | 14 |
| course_visits | 35.5837055 | 70.7518683 | 76.40201957999997 | 20.725437822178222 | 0 | 212 |
| enrollments | 8.196232 | 11.862307849999999 | 12.628795720000001 | 23.76562262517474 | 0 | 242 |
| gaze_batch | 36.184841 | 53.07606355 | 54.87644513 | 7.69230631139078 | 0 | 80 |
| lesson_contents | 16.798515000000002 | 34.493512149999994 | 40.840621450000015 | 22.78264645375851 | 0 | 230 |
| outline | 15.436152 | 20.9499589 | 24.40384061999999 | 23.28141330854175 | 0 | 235 |
| replay | 53.415807 | 60.5299602 | 75.81350381 | 7.964303953046647 | 0 | 80 |
| samples | 18.337073500000002 | 30.545115749999994 | 57.97288631 | 22.565647080558946 | 0 | 230 |
| session_contents | 14.552413999999999 | 34.786608149999864 | 43.50324269000001 | 22.905850741386182 | 0 | 230 |
| teacher_courses | 33.4146755 | 45.51259525 | 52.54304465 | 8.573055261099574 | 0 | 86 |

### Queries mỗi request

| endpoint | queries_total | iterations | queries_per_request |
|---|---|---|---|
| aoi_summary | 274 | 20 | 13.7 |
| course_students | 256 | 20 | 12.8 |
| course_visits | 184 | 20 | 9.2 |
| enrollments | 30 | 20 | 1.5 |
| outline | 146 | 20 | 7.3 |
| replay | 305 | 20 | 15.25 |
| samples | 224 | 20 | 11.2 |
| session_contents | 265 | 20 | 13.25 |
| teacher_courses | 185 | 20 | 9.25 |

## Gaze

- device: `cuda:0` / `fp32` / `unigaze_b16_joint`

| image | count | p50 | p95 | p99 |
|---|---|---|---|---|
| 480px | 50 | 10.962 | 11.329 | 11.415 |
| 720px | 50 | 11.68 | 12.411 | 12.674 |
| 1080px | 50 | 13.187 | 13.325 | 13.692 |

### Gaze WebSocket

| sessions | resp/s | fps/session | drop | p95 | p99 |
|---|---|---|---|---|---|
| 1 | 14.7 | 14.7 | 0.02 | 45.004 | 46.051 |
| 4 | 58.1 | 14.53 | 0.0317 | 29.204 | 33.295 |
| 8 | 107.9 | 13.49 | 0.1008 | 145.462 | 151.737 |

## Chatbot

### Query trực tiếp

| concurrency | rps | ttft_p95 | total_p95 | error |
|---|---|---|---|---|
| 1 | 0.024 | 34692.18 | 63612.96 | 0.0 |
| 5 | 0.075 | 35655.2 | 64049.65 | 0.125 |

### Ingest

- slides: 2 / processed: 2 / wall: 25439.55 ms

| stage | p50 | p95 | mean |
|---|---|---|---|
| pdf_render | 57.85 | 57.85 | 54.4 |
| vlm | 10739.37 | 10739.37 | 10210.45 |
| embedding | 8161.31 | 8161.31 | 7839.85 |
| db_upsert | 16.81 | 16.81 | 15.87 |
| db_mark | 8.83 | 8.83 | 5.4 |

## Frontend

- static raw: 4143473 bytes / gzip: 2005967 bytes

## Redis

- hit rate before: 0.968473
- hit rate after: 0.972557
