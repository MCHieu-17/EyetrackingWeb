# Benchmark summary — 20261121T125103Z-phase51

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
| aoi_summary | 193.7268615 | 218.93788684999996 | 231.37586825 | 5.061206701219604 | 0 | 52 |
| course_visits | 32.286088 | 58.639353399999955 | 76.5082484 | 21.104054603887235 | 0 | 215 |
| enrollments | 5.341876 | 7.225411299999998 | 31.26188168 | 24.090885854154646 | 0 | 243 |
| gaze_batch | 10.0489245 | 16.55794655 | 17.923834659999997 | 7.896808068098758 | 0 | 80 |
| lesson_contents | 15.519953 | 22.366053599999997 | 27.68313224 | 23.07226607633452 | 0 | 235 |
| outline | 8.874611000000002 | 19.9026972 | 75.95944201999997 | 23.484258194675434 | 0 | 240 |
| replay | 40.481438 | 67.19859704999993 | 80.21124430000005 | 8.258838434498378 | 0 | 84 |
| samples | 14.940732 | 30.7925641 | 46.414793070000016 | 22.863083805328525 | 0 | 230 |
| session_contents | 15.507015 | 22.135120999999998 | 26.273036840000003 | 23.20263310618535 | 0 | 233 |
| teacher_courses | 40.4501575 | 50.14722789999999 | 54.989593550000016 | 8.397637058608465 | 0 | 84 |

### Queries mỗi request

| endpoint | queries_total | iterations | queries_per_request |
|---|---|---|---|
| aoi_summary | 312 | 20 | 15.6 |
| course_students | 290 | 20 | 14.5 |
| course_visits | 245 | 20 | 12.25 |
| enrollments | 83 | 20 | 4.15 |
| outline | 188 | 20 | 9.4 |
| replay | 350 | 20 | 17.5 |
| samples | 272 | 20 | 13.6 |
| session_contents | 313 | 20 | 15.65 |
| teacher_courses | 244 | 20 | 12.2 |

## Redis

- hit rate before: 0.910581
- hit rate after: 0.935583
