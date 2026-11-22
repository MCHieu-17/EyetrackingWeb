# Benchmark summary — 20261121T0600Z-phase1

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
| aoi_summary | 185.6075835 | 220.53239729999999 | 240.76717635000003 | 5.1447980405324305 | 0 | 52 |
| course_visits | 28.0426115 | 57.14573009999999 | 66.67222303000001 | 21.579595322616044 | 0 | 220 |
| enrollments | 6.345084 | 11.440810649999998 | 50.93253332000013 | 23.988121106218074 | 0 | 242 |
| gaze_batch | 34.627303 | 78.9967669 | 83.15040689 | 7.680192674283893 | 0 | 80 |
| lesson_contents | 13.022165 | 24.5558838 | 34.485498359999994 | 23.152767467349605 | 0 | 235 |
| outline | 13.8531 | 21.5742637 | 44.403877359999925 | 23.143102151718626 | 0 | 235 |
| replay | 53.258306000000005 | 63.948375850000005 | 85.90397788999998 | 7.990823239583413 | 0 | 82 |
| samples | 16.4599465 | 31.863926499999984 | 53.639180170000046 | 22.72638501940318 | 0 | 230 |
| session_contents | 12.899655 | 30.685655699999995 | 34.76876784 | 23.099833340403684 | 0 | 235 |
| teacher_courses | 23.5873875 | 48.6415711 | 63.316722729999995 | 8.662793310351361 | 0 | 88 |

### Queries mỗi request

| endpoint | queries_total | iterations | queries_per_request |
|---|---|---|---|
| aoi_summary | 222 | 20 | 11.1 |
| course_students | 224 | 20 | 11.2 |
| course_visits | 184 | 20 | 9.2 |
| enrollments | 29 | 20 | 1.45 |
| outline | 140 | 20 | 7.0 |
| replay | 284 | 20 | 14.2 |
| samples | 231 | 20 | 11.55 |
| session_contents | 264 | 20 | 13.2 |
| teacher_courses | 185 | 20 | 9.25 |

## Redis

- hit rate before: None
- hit rate after: 0.98581
