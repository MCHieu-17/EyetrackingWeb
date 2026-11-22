# Benchmark summary — 20261122T-post-chat-layout

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
| add-students | 8.768663499999999 | 17.2427368 | 17.32482976 | 4.737823593546875 | 0 | 10 |
| aoi_summary | 19.207922 | 35.558203 | 51.99432306 | 8.972633359684101 | 0 | 90 |
| auth-me | 8.2624755 | 9.9604994 | 10.348216520000001 | 4.797934599507408 | 0 | 48 |
| course_students | 7.028786 | 13.320397 | 15.815567599999998 | 23.607633970975 | 0 | 241 |
| course_visits | 8.184644 | 14.374281 | 17.847150469999995 | 23.648935135990115 | 0 | 240 |
| enrollments | 4.455196 | 7.162146 | 70.57548934 | 24.005774717731885 | 0 | 243 |
| gaze_batch | 18.734154 | 36.47236905 | 38.14502776999998 | 7.821480756344686 | 0 | 80 |
| gaze_batch_nginx | 36.246355 | 69.20630105 | 77.07612191 | 19.405474485577912 | 0 | 210 |
| lesson_contents | 13.063862 | 19.2653254 | 21.110022679999997 | 23.341170460915237 | 0 | 237 |
| outline | 8.637404 | 13.618511699999999 | 16.12397134999998 | 23.5135881295958 | 0 | 240 |
| replay | 10.100307 | 14.0589935 | 36.431919300000004 | 9.476335044431588 | 0 | 96 |
| samples | 13.9726945 | 21.11085425 | 26.232179200000004 | 23.130608441813486 | 0 | 236 |
| session_contents | 12.038307 | 18.78787644999999 | 24.004299729999996 | 23.445166711891225 | 0 | 238 |
| teacher_courses | 7.9600845 | 13.08262375 | 14.1062836 | 9.5383772508178 | 0 | 96 |

### Queries mỗi request

| endpoint | queries_total | iterations | queries_per_request |
|---|---|---|---|
| aoi_summary | 259 | 20 | 12.95 |
| course_students | 175 | 20 | 8.75 |
| course_visits | 173 | 20 | 8.65 |
| enrollments | 65 | 20 | 3.25 |
| outline | 169 | 20 | 8.45 |
| replay | 155 | 20 | 7.75 |
| samples | 212 | 20 | 10.6 |
| session_contents | 223 | 20 | 11.15 |
| teacher_courses | 179 | 20 | 8.95 |

### Auth memory-hit

- p50/p95/p99: 0.0011789998097810894 / 0.0012740019883494824 / 0.0022519998310599476 ms
- Redis GET/call: 0.0 (0 / 500)

## Frontend

- static raw: 4149876 bytes / gzip: 2008426 bytes

## Redis

- hit rate before: None
- hit rate after: 0.962168
