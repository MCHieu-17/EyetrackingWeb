# Benchmark summary — 20261121T180700Z-phase6

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
| aoi_summary | 180.9492275 | 222.85217515 | 230.82877231 | 5.162673146248246 | 0 | 52 |
| course_visits | 28.87804 | 64.8023436 | 70.09580872 | 21.22660153566546 | 0 | 215 |
| enrollments | 4.462339 | 7.3935846 | 31.967037040000015 | 24.041464876945415 | 0 | 245 |
| gaze_batch | 16.841411 | 31.836513349999997 | 67.77707467999997 | 7.835665161531115 | 0 | 80 |
| lesson_contents | 10.615905 | 21.801122699999997 | 37.25314315999999 | 23.11265978144748 | 0 | 235 |
| outline | 9.8408525 | 15.720825849999999 | 55.353687849999986 | 23.53905770752002 | 0 | 238 |
| replay | 39.365080000000006 | 56.420580799999996 | 76.21731998000001 | 8.31350318943398 | 0 | 84 |
| samples | 15.139732 | 25.15070499999999 | 44.77777548000016 | 22.913310900423106 | 0 | 233 |
| session_contents | 13.214194 | 22.550184199999993 | 24.53811808 | 23.17005091310815 | 0 | 233 |
| teacher_courses | 38.663022 | 48.8128535 | 78.08986955 | 8.431529092756524 | 0 | 86 |

### Queries mỗi request

| endpoint | queries_total | iterations | queries_per_request |
|---|---|---|---|
| aoi_summary | 300 | 20 | 15.0 |
| course_students | 291 | 20 | 14.55 |
| course_visits | 236 | 20 | 11.8 |
| enrollments | 77 | 20 | 3.85 |
| outline | 188 | 20 | 9.4 |
| replay | 353 | 20 | 17.65 |
| samples | 273 | 20 | 13.65 |
| session_contents | 312 | 20 | 15.6 |
| teacher_courses | 250 | 20 | 12.5 |

## Redis

- hit rate before: None
- hit rate after: 0.977862
