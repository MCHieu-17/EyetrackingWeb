# Benchmark comparison

- baseline: `benchmarks/baseline/20261122T0520Z-phase8`
- after: `benchmarks/baseline/20261122T0530Z-phase9`

| Metric | Baseline | After | Delta |
|---|---:|---:|---:|
| backend.query_counts.aoi_summary.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.aoi_summary.queries_per_request | 15.300 | 15.600 | +1.96% |
| backend.query_counts.aoi_summary.queries_total | 306.000 | 312.000 | +1.96% |
| backend.query_counts.course_students.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.course_students.queries_per_request | 11.950 | 9.050 | -24.27% |
| backend.query_counts.course_students.queries_total | 239.000 | 181.000 | -24.27% |
| backend.query_counts.course_visits.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.course_visits.queries_per_request | 10.200 | 8.650 | -15.20% |
| backend.query_counts.course_visits.queries_total | 204.000 | 173.000 | -15.20% |
| backend.query_counts.enrollments.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.enrollments.queries_per_request | 3.850 | 3.850 | +0.00% |
| backend.query_counts.enrollments.queries_total | 77.000 | 77.000 | +0.00% |
| backend.query_counts.outline.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.outline.queries_per_request | 10.000 | 9.100 | -9.00% |
| backend.query_counts.outline.queries_total | 200.000 | 182.000 | -9.00% |
| backend.query_counts.replay.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.replay.queries_per_request | 11.200 | 7.750 | -30.80% |
| backend.query_counts.replay.queries_total | 224.000 | 155.000 | -30.80% |
| backend.query_counts.samples.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.samples.queries_per_request | 10.900 | 10.600 | -2.75% |
| backend.query_counts.samples.queries_total | 218.000 | 212.000 | -2.75% |
| backend.query_counts.session_contents.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.session_contents.queries_per_request | 11.900 | 11.900 | +0.00% |
| backend.query_counts.session_contents.queries_total | 238.000 | 238.000 | +0.00% |
| backend.query_counts.teacher_courses.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.teacher_courses.queries_per_request | 8.650 | 8.950 | +3.47% |
| backend.query_counts.teacher_courses.queries_total | 173.000 | 179.000 | +3.47% |
| fixtures.counts.aois | 243.000 | 243.000 | +0.00% |
| fixtures.counts.background_jobs | 100.000 | 100.000 | +0.00% |
| fixtures.counts.chat_messages | 2000.000 | 2000.000 | +0.00% |
| fixtures.counts.chat_sessions | 200.000 | 200.000 | +0.00% |
| fixtures.counts.content_views | 19240.000 | 19240.000 | +0.00% |
| fixtures.counts.course_modules | 21.000 | 21.000 | +0.00% |
| fixtures.counts.course_visits | 419.000 | 419.000 | +0.00% |
| fixtures.counts.courses | 6.000 | 6.000 | +0.00% |
| fixtures.counts.enrollments | 400.000 | 400.000 | +0.00% |
| fixtures.counts.gaze_calibrations | 100.000 | 100.000 | +0.00% |
| fixtures.counts.gaze_samples | 3445200.000 | 3445200.000 | +0.00% |
| fixtures.counts.learning_sessions | 1057.000 | 1057.000 | +0.00% |
| fixtures.counts.lessons | 105.000 | 105.000 | +0.00% |
| fixtures.counts.quiz_attempts | 1000.000 | 1000.000 | +0.00% |
| fixtures.counts.slides | 540.000 | 540.000 | +0.00% |
| fixtures.counts.users | 202.000 | 202.000 | +0.00% |
| fixtures.counts.view_layouts | 160.000 | 160.000 | +0.00% |
| redis.after.evicted_keys | 0.000 | 0.000 | - |
| redis.after.expired_keys | 69.000 | 194.000 | +181.16% |
| redis.after.hit_rate | 0.976 | 0.964 | -1.23% |
| redis.after.instantaneous_ops_per_sec | 100.000 | 0.000 | -100.00% |
| redis.after.keyspace_hits | 3573.000 | 6790.000 | +90.04% |
| redis.after.keyspace_misses | 88.000 | 254.000 | +188.64% |
| redis.after.total_commands_processed | 20617.000 | 404780.000 | +1863.33% |
| redis.before.evicted_keys | 0.000 | 0.000 | - |
| redis.before.expired_keys | 36.000 | 143.000 | +297.22% |
| redis.before.hit_rate | 0.972 | 0.969 | -0.26% |
| redis.before.instantaneous_ops_per_sec | 0.000 | 0.000 | - |
| redis.before.keyspace_hits | 1263.000 | 4658.000 | +268.80% |
| redis.before.keyspace_misses | 37.000 | 149.000 | +302.70% |
| redis.before.total_commands_processed | 1939.000 | 398546.000 | +20454.20% |
