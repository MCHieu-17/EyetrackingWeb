# Benchmark summary — pre-ui

## Dataset

| Table | Rows |
|---|---:|
| users | 21 |
| courses | 8 |
| course_modules | 17 |
| lessons | 70 |
| slides | 342 |
| aois | 244 |
| enrollments | 17 |
| course_visits | 48 |
| learning_sessions | 77 |
| content_views | 218 |
| view_layouts | 20 |
| gaze_samples | 3,220 |
| chat_sessions | 12 |
| chat_messages | 120 |
| quiz_attempts | 44 |
| gaze_calibrations | 8 |
| background_jobs | 21 |

## Frontend

- static raw: 4155298 bytes / gzip: 2009749 bytes

### Lighthouse

| page | form | score | a11y | best_practices | lcp | tbt | ttfb |
|---|---|---|---|---|---|---|---|
| admin | desktop | 1 | 0.96 | 1 | 281.2164 | 0 | 3 |
| admin | mobile | 1 | 0.96 | 1 | 1050.7416 | 79.11862500000075 | 3 |
| home | desktop | 1 | 0.96 | 1 | 280.5684 | 0 | 2 |
| home | mobile | 1 | 0.96 | 1 | 1050.6644 | 75.85562500000015 | 2 |
| login | desktop | 1 | 0.96 | 1 | 280.4994 | 0 | 3 |
| login | mobile | 1 | 0.96 | 1 | 1050.7504 | 73.82002499999999 | 3 |
| student_reader | desktop | 1 | 0.88 | 0.96 | 280.6655 | 0 | 6 |
| student_reader | mobile | 0.98 | 0.76 | 0.96 | 1050.8075 | 151 | 6 |
| student | desktop | 1 | 0.96 | 1 | 280.6334 | 0 | 3 |
| student | mobile | 0.99 | 0.96 | 1 | 1050.6475 | 122.5 | 2 |
| teacher_analytics | desktop | 0.98 | 0.96 | 1 | 1125.7669999999996 | 0 | 6 |
| teacher_analytics | mobile | 0.79 | 0.96 | 1 | 5729.412600000001 | 97.5 | 6 |
| teacher_workspace | desktop | 0.99 | 0.96 | 1 | 945.2932499999997 | 0 | 7 |
| teacher_workspace | mobile | 0.8 | 1 | 1 | 4928.92725 | 162.5 | 7 |
| teacher | desktop | 1 | 0.96 | 1 | 280.5046 | 0 | 3 |
| teacher | mobile | 1 | 0.96 | 1 | 1050.7711 | 49.5 | 3 |
| try | desktop | 1 | 0.96 | 1 | 280.4197 | 0 | 2 |
| try | mobile | 1 | 0.96 | 1 | 1050.4773 | 37.5 | 1 |
