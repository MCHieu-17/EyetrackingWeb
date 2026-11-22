# Benchmark summary — 20261122T0520Z-phase8

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
| aoi_summary | 191.65319399999998 | 227.66477555 | 234.95712763 | 5.055139091010795 | 0 | 52 |
| course_visits | 28.574707 | 55.647501600000005 | 60.03730033999999 | 21.387562838135608 | 0 | 215 |
| enrollments | 6.00354 | 7.3151893999999995 | 41.60645460000001 | 24.051552879872766 | 0 | 245 |
| gaze_batch | 12.634106500000001 | 37.66432869999999 | 41.84190491999999 | 7.852257076433883 | 0 | 80 |
| lesson_contents | 13.400407 | 19.728944799999997 | 22.788909479999997 | 23.353958707147257 | 0 | 237 |
| outline | 9.861003 | 15.6523161 | 39.939431169999935 | 23.633762846563634 | 0 | 238 |
| replay | 29.427978500000002 | 48.227818899999995 | 68.32710633999989 | 8.619430485399752 | 0 | 88 |
| samples | 13.743766 | 30.458524 | 46.68808099999992 | 22.600568428383678 | 0 | 231 |
| session_contents | 10.844033 | 19.0999993 | 32.47858722999998 | 23.501020468815327 | 0 | 238 |
| teacher_courses | 9.822348 | 12.74641425 | 28.19019875 | 9.503515564880017 | 0 | 96 |

### Queries mỗi request

| endpoint | queries_total | iterations | queries_per_request |
|---|---|---|---|
| aoi_summary | 306 | 20 | 15.3 |
| course_students | 239 | 20 | 11.95 |
| course_visits | 204 | 20 | 10.2 |
| enrollments | 77 | 20 | 3.85 |
| outline | 200 | 20 | 10.0 |
| replay | 224 | 20 | 11.2 |
| samples | 218 | 20 | 10.9 |
| session_contents | 238 | 20 | 11.9 |
| teacher_courses | 173 | 20 | 8.65 |

## Redis

- hit rate before: 0.971538
- hit rate after: 0.975963
