# Benchmark summary — 20261122T1640Z-after-10phase

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
| add-students | 28.537824 | 52.10046829999998 | 59.59572086000001 | 4.323186517717443 | 0 | 10 |
| aoi_summary | 184.295805 | 222.60046595 | 229.06988966 | 5.11762180858173 | 0 | 52 |
| auth-me | 7.740961 | 9.8806223 | 10.17730355 | 4.795101113238756 | 0 | 48 |
| course_students | 7.763568 | 15.868935 | 43.699499749999994 | 23.677311083007233 | 0 | 238 |
| course_visits | 13.183992 | 19.692995199999995 | 66.66568882 | 23.11225335254791 | 0 | 235 |
| enrollments | 4.39772 | 7.306103799999999 | 64.69771265999951 | 24.034044227208437 | 0 | 243 |
| gaze_batch | 9.224475 | 27.794891699999997 | 29.681409439999978 | 7.8877927897326625 | 0 | 80 |
| gaze_batch_nginx | 12.8904915 | 67.65930494999995 | 73.61015037 | 19.60909510382524 | 0 | 210 |
| lesson_contents | 10.7962355 | 19.0916119 | 19.42620358 | 23.532590977033053 | 0 | 238 |
| outline | 8.008075999999999 | 13.4489618 | 18.71928425 | 23.636110003713398 | 0 | 240 |
| replay | 15.2189495 | 25.517918499999997 | 31.300348549999995 | 9.259218405420603 | 0 | 94 |
| samples | 19.316633500000002 | 27.135750799999997 | 56.15524157000002 | 22.550059114720153 | 0 | 230 |
| session_contents | 11.504901 | 18.5802002 | 19.45549032 | 23.32179309962541 | 0 | 238 |
| teacher_courses | 8.0719885 | 12.764422249999999 | 36.10305595 | 9.541820210212538 | 0 | 96 |

### Queries mỗi request

| endpoint | queries_total | iterations | queries_per_request |
|---|---|---|---|
| aoi_summary | 300 | 20 | 15.0 |
| course_students | 163 | 20 | 8.15 |
| course_visits | 173 | 20 | 8.65 |
| enrollments | 77 | 20 | 3.85 |
| outline | 175 | 20 | 8.75 |
| replay | 161 | 20 | 8.05 |
| samples | 219 | 20 | 10.95 |
| session_contents | 232 | 20 | 11.6 |
| teacher_courses | 174 | 20 | 8.7 |

### Auth memory-hit

- p50/p95/p99: 0.0011930005712201819 / 0.0012580003385664895 / 0.002310000127181411 ms
- Redis GET/call: 0.0 (0 / 500)

## Gaze

- device: `cuda:0` / `fp16` / `unigaze_b16_joint`

| image | count | p50 | p95 | p99 |
|---|---|---|---|---|
| 480px | 50 | 6.587 | 6.931 | 7.516 |
| 720px | 50 | 7.198 | 7.812 | 9.013 |
| 1080px | 50 | 8.56 | 9.195 | 11.072 |

### Gaze WebSocket

| sessions | resp/s | fps/session | drop | p95 | p99 |
|---|---|---|---|---|---|
| 1 | 14.2 | 14.2 | 0.0533 | 45.951 | 48.276 |
| 4 | 59.3 | 14.82 | 0.0117 | 29.959 | 34.092 |
| 8 | 120.0 | 15.0 | 0.0 | 21.055 | 23.827 |

## Chatbot

### Query trực tiếp

| concurrency | rps | ttft_p95 | total_p95 | error |
|---|---|---|---|---|
| 1 | 0.15 | 758.59 | 8028.5 | 0.0 |
| 5 | 0.584 | 368.36 | 10725.78 | 0.0 |

### Ingest

- slides: 2 / processed: 2 / wall: 7413.05 ms

| stage | p50 | p95 | mean |
|---|---|---|---|
| pdf_render | 30.9 | 30.9 | 27.86 |
| vlm | 3284.65 | 3284.65 | 3263.55 |
| embedding | 2042.4 | 2042.4 | 2042.4 |
| db_upsert | 3.64 | 3.64 | 3.59 |
| db_mark | None | None | None |

## Frontend

- static raw: 4149876 bytes / gzip: 2008426 bytes

## Redis

- hit rate before: None
- hit rate after: 0.952724
