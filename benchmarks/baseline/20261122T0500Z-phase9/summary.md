# Benchmark summary — 20261122T0500Z-phase9

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
| add-students | 23.0745925 | 36.201550000000005 | 1042.44751911 | 8.049272486776706 | 0.012195121951219513 | 82 |
| aoi_summary | 190.57926650000002 | 227.70697934999998 | 239.17309579 | 5.072599608459733 | 0 | 52 |
| auth-me | 8.363681 | 9.7057162 | 9.853684659999999 | 4.789698291529178 | 0 | 48 |
| course_visits | 13.138828 | 19.7734347 | 57.10910954 | 23.04146298115117 | 0 | 235 |
| enrollments | 4.521915 | 7.424732799999998 | 34.35333396000007 | 24.059000448897642 | 0 | 245 |
| gaze_batch | 10.5056725 | 41.8919662 | 45.43374797999999 | 7.845970535629253 | 0 | 80 |
| gaze_batch_nginx | 49.4022815 | 82.14558029999999 | 92.34570851000001 | 19.290252499691203 | 0 | 210 |
| lesson_contents | 12.856615 | 19.0301524 | 21.96694953 | 23.425800343740924 | 0 | 238 |
| outline | 8.953367499999999 | 13.801634349999999 | 33.92064278999954 | 23.52879571624518 | 0 | 240 |
| replay | 16.237693 | 22.220797149999996 | 50.12766253 | 9.239043375975575 | 0 | 94 |
| samples | 16.876612 | 31.445107999999998 | 45.135594599999884 | 22.60901662837864 | 0 | 231 |
| session_contents | 12.634304499999999 | 19.1024379 | 23.03365078999999 | 23.30952308969421 | 0 | 238 |
| teacher_courses | 9.255415 | 13.8166825 | 38.041314 | 9.493610423456795 | 0 | 96 |

### Queries mỗi request

| endpoint | queries_total | iterations | queries_per_request |
|---|---|---|---|
| aoi_summary | 313 | 20 | 15.65 |
| course_students | 181 | 20 | 9.05 |
| course_visits | 173 | 20 | 8.65 |
| enrollments | 84 | 20 | 4.2 |
| outline | 181 | 20 | 9.05 |
| replay | 155 | 20 | 7.75 |
| samples | 212 | 20 | 10.6 |
| session_contents | 232 | 20 | 11.6 |
| teacher_courses | 179 | 20 | 8.95 |

## Redis

- hit rate before: None
- hit rate after: 0.96883
