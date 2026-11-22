# Benchmark summary — 20261122T0530Z-phase9

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
| add-students | 26.6191675 | 29.26290985 | 29.56773157 | 4.444873752081914 | 0 | 10 |
| aoi_summary | 179.675851 | 225.88553879999998 | 235.98942531999998 | 5.103755912669326 | 0 | 53 |
| auth-me | 9.056041 | 9.93044045 | 10.03818982 | 4.780284138258728 | 0 | 48 |
| course_students | 8.346415499999999 | 15.6833879 | 37.48415490999999 | 23.62434772767709 | 0 | 238 |
| course_visits | 9.551123 | 19.23289675 | 25.101778519999996 | 23.514379899212038 | 0 | 238 |
| enrollments | 4.597338 | 7.2828114 | 8.888275320000002 | 24.12863321424898 | 0 | 245 |
| gaze_batch | 10.540557 | 25.383442999999996 | 30.851921469999976 | 7.860483065340256 | 0 | 80 |
| gaze_batch_nginx | 35.964047 | 82.29315685 | 90.54759994 | 19.34617957901399 | 0 | 210 |
| lesson_contents | 9.582224 | 19.381693849999998 | 21.56902366 | 23.547872104492107 | 0 | 238 |
| outline | 7.348449 | 12.829322599999998 | 14.097301119999997 | 23.86636925912434 | 0 | 243 |
| replay | 15.0518685 | 23.147738999999998 | 23.975944749999982 | 9.307304279969468 | 0 | 94 |
| samples | 17.5569745 | 27.3775032 | 46.915165019999996 | 22.731894127138638 | 0 | 232 |
| session_contents | 9.530594 | 17.655096399999998 | 18.83017108 | 23.59288454050641 | 0 | 238 |
| teacher_courses | 8.404921 | 13.18744925 | 20.604406549999986 | 9.521476949930392 | 0 | 96 |

### Queries mỗi request

| endpoint | queries_total | iterations | queries_per_request |
|---|---|---|---|
| aoi_summary | 312 | 20 | 15.6 |
| course_students | 181 | 20 | 9.05 |
| course_visits | 173 | 20 | 8.65 |
| enrollments | 77 | 20 | 3.85 |
| outline | 182 | 20 | 9.1 |
| replay | 155 | 20 | 7.75 |
| samples | 212 | 20 | 10.6 |
| session_contents | 238 | 20 | 11.9 |
| teacher_courses | 179 | 20 | 8.95 |

### Auth memory-hit

- p50/p95/p99: 0.0011190004443051293 / 0.001217000317410566 / 0.0020000006770715117 ms
- Redis GET/call: 0.0 (0 / 500)

## Redis

- hit rate before: 0.969004
- hit rate after: 0.963941
