# Benchmark summary — 20261121T121112Z-phase5

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
| aoi_summary | 183.968603 | 230.57866939999997 | 245.11093792000003 | 5.132543290966175 | 0 | 52 |
| course_visits | 42.039237 | 75.0550014 | 79.66293852000003 | 20.379938229628035 | 0 | 205 |
| enrollments | 5.109758 | 8.650888199999999 | 22.52614668 | 24.106251833323498 | 0 | 245 |
| gaze_batch | 22.535698500000002 | 38.70208435 | 40.84933573999999 | 7.786671604205513 | 0 | 80 |
| lesson_contents | 18.4359605 | 27.676307799999996 | 30.65644508 | 22.763416745804957 | 0 | 230 |
| outline | 11.1322085 | 18.063892799999998 | 24.976603739999995 | 23.55060101459342 | 0 | 238 |
| replay | 45.255388499999995 | 59.4977557 | 81.71637760000002 | 8.196742121666327 | 0 | 84 |
| samples | 24.799996 | 40.181644399999996 | 54.94416188000002 | 21.970480491770914 | 0 | 223 |
| session_contents | 22.016455999999998 | 29.206421699999996 | 39.07326486 | 22.57129395872686 | 0 | 230 |
| teacher_courses | 36.2516085 | 49.609663999999995 | 51.85768875 | 8.416591379098683 | 0 | 86 |

### Queries mỗi request

| endpoint | queries_total | iterations | queries_per_request |
|---|---|---|---|
| aoi_summary | 313 | 20 | 15.65 |
| course_students | 290 | 20 | 14.5 |
| course_visits | 244 | 20 | 12.2 |
| enrollments | 84 | 20 | 4.2 |
| outline | 194 | 20 | 9.7 |
| replay | 344 | 20 | 17.2 |
| samples | 278 | 20 | 13.9 |
| session_contents | 318 | 20 | 15.9 |
| teacher_courses | 232 | 20 | 11.6 |

## Redis

- hit rate before: 0.971672
- hit rate after: 0.975754
