# Benchmark summary — 20261122T-pre-chat-layout

## Dataset

| Table | Rows |
|---|---:|
| users | 18 |
| courses | 4 |
| course_modules | 13 |
| lessons | 65 |
| slides | 340 |
| aois | 243 |
| enrollments | 16 |
| course_visits | 24 |
| learning_sessions | 40 |
| content_views | 168 |
| view_layouts | 18 |
| gaze_samples | 3,200 |
| chat_sessions | 12 |
| chat_messages | 120 |
| quiz_attempts | 40 |
| gaze_calibrations | 8 |
| background_jobs | 10 |

## Backend (k6)

| scenario | p50 | p95 | p99 | rps | error_rate | count |
|---|---|---|---|---|---|---|
| add-students | 10.8658415 | 16.9543188 | 17.72902296 | 4.702466222564847 | 0 | 10 |
| aoi_summary | 22.25804 | 38.0706593 | 46.06075423 | 8.861251738697588 | 0 | 90 |
| auth-me | 8.4439915 | 10.22169545 | 10.489606960000001 | 4.796485072425324 | 0 | 48 |
| course_students | 7.807943 | 11.775510899999999 | 13.563066039999999 | 23.85705408092118 | 0 | 243 |
| course_visits | 8.733941 | 13.8916658 | 15.947666179999999 | 23.597237139159688 | 0 | 240 |
| enrollments | 4.485364 | 7.2459115 | 76.79546898 | 23.99889732355352 | 0 | 243 |
| gaze_batch | 21.8679355 | 31.965951899999997 | 33.02795734 | 7.827007580213227 | 0 | 80 |
| gaze_batch_nginx | 31.685793500000003 | 82.35187274999998 | 103.41272865999998 | 19.403260725319647 | 0 | 210 |
| lesson_contents | 12.1419775 | 20.38486554999999 | 36.423609289999995 | 23.40570164253083 | 0 | 238 |
| outline | 7.95279 | 12.982115 | 32.71668395999954 | 23.676024529931134 | 0 | 240 |
| replay | 7.608173 | 14.85555125 | 21.12096185 | 9.522194757957632 | 0 | 96 |
| samples | 15.39716 | 21.0629466 | 22.2840668 | 23.10157946208685 | 0 | 233 |
| session_contents | 11.4728265 | 18.4277096 | 19.69995598 | 23.546055173339674 | 0 | 238 |
| teacher_courses | 7.4515445 | 12.444661499999999 | 14.9991978 | 9.584435221281863 | 0 | 96 |

### Queries mỗi request

| endpoint | queries_total | iterations | queries_per_request |
|---|---|---|---|
| aoi_summary | 264 | 20 | 13.2 |
| course_students | 181 | 20 | 9.05 |
| course_visits | 179 | 20 | 8.95 |
| enrollments | 72 | 20 | 3.6 |
| outline | 175 | 20 | 8.75 |
| replay | 162 | 20 | 8.1 |
| samples | 218 | 20 | 10.9 |
| session_contents | 238 | 20 | 11.9 |
| teacher_courses | 173 | 20 | 8.65 |

### Auth memory-hit

- p50/p95/p99: 0.001186999725177884 / 0.0012609998520929366 / 0.0021699997887481004 ms
- Redis GET/call: 0.0 (0 / 500)

## Frontend

- static raw: 4149680 bytes / gzip: 2008363 bytes

## Redis

- hit rate before: None
- hit rate after: 0.961696
