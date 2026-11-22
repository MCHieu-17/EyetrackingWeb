# Benchmark summary — 20261122T-post2-chat-layout

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
| add-students | 16.879295499999998 | 17.76610355 | 18.19042151 | 4.623480659353227 | 0 | 10 |
| aoi_summary | 27.112043999999997 | 34.16283155 | 36.73004821 | 8.84635246427035 | 0 | 90 |
| auth-me | 8.433015000000001 | 10.021841049999999 | 10.12066333 | 4.78869246574819 | 0 | 48 |
| course_students | 7.560058 | 12.250279299999999 | 15.846810859999955 | 23.86484919649912 | 0 | 243 |
| course_visits | 8.871822 | 14.52084555 | 17.233877989999968 | 23.52749590687448 | 0 | 240 |
| enrollments | 4.40467 | 7.276587999999999 | 32.949676880000055 | 24.131763528705612 | 0 | 245 |
| gaze_batch | 9.642199 | 34.7029213 | 36.68358881999998 | 7.872223024348174 | 0 | 80 |
| gaze_batch_nginx | 27.434510500000002 | 66.96400489999999 | 75.33995481 | 19.48031463181945 | 0 | 210 |
| lesson_contents | 12.304807 | 19.516579949999993 | 21.53340267 | 23.341646012034772 | 0 | 238 |
| outline | 8.5874425 | 13.55028425 | 34.08837674999962 | 23.58250117919458 | 0 | 240 |
| replay | 9.5094195 | 13.85304425 | 35.47614204999999 | 9.496294581168772 | 0 | 96 |
| samples | 13.3141155 | 22.614575000000002 | 32.31289115000004 | 23.186357781601533 | 0 | 236 |
| session_contents | 11.3530345 | 19.121686549999996 | 22.63726634 | 23.448398401319846 | 0 | 238 |
| teacher_courses | 7.8871445 | 12.35551225 | 16.623186750000002 | 9.561388292509163 | 0 | 96 |

### Queries mỗi request

| endpoint | queries_total | iterations | queries_per_request |
|---|---|---|---|
| aoi_summary | 265 | 20 | 13.25 |
| course_students | 163 | 20 | 8.15 |
| course_visits | 179 | 20 | 8.95 |
| enrollments | 78 | 20 | 3.9 |
| outline | 181 | 20 | 9.05 |
| replay | 155 | 20 | 7.75 |
| samples | 218 | 20 | 10.9 |
| session_contents | 232 | 20 | 11.6 |
| teacher_courses | 173 | 20 | 8.65 |

### Auth memory-hit

- p50/p95/p99: 0.0012040000001434237 / 0.0012880009307991713 / 0.00279700179817155 ms
- Redis GET/call: 0.0 (0 / 500)

## Redis

- hit rate before: None
- hit rate after: 0.963209
