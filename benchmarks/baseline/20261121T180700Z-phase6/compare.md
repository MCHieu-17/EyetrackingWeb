# Benchmark comparison

- baseline: `benchmarks/baseline/20261120T180000Z-baseline`
- after: `benchmarks/baseline/20261121T180700Z-phase6`

| Metric | Baseline | After | Delta |
|---|---:|---:|---:|
| backend.query_counts.aoi_summary.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.aoi_summary.queries_per_request | 13.700 | 15.000 | +9.49% |
| backend.query_counts.aoi_summary.queries_total | 274.000 | 300.000 | +9.49% |
| backend.query_counts.course_students.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.course_students.queries_per_request | 12.800 | 14.550 | +13.67% |
| backend.query_counts.course_students.queries_total | 256.000 | 291.000 | +13.67% |
| backend.query_counts.course_visits.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.course_visits.queries_per_request | 9.200 | 11.800 | +28.26% |
| backend.query_counts.course_visits.queries_total | 184.000 | 236.000 | +28.26% |
| backend.query_counts.enrollments.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.enrollments.queries_per_request | 1.500 | 3.850 | +156.67% |
| backend.query_counts.enrollments.queries_total | 30.000 | 77.000 | +156.67% |
| backend.query_counts.outline.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.outline.queries_per_request | 7.300 | 9.400 | +28.77% |
| backend.query_counts.outline.queries_total | 146.000 | 188.000 | +28.77% |
| backend.query_counts.replay.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.replay.queries_per_request | 15.250 | 17.650 | +15.74% |
| backend.query_counts.replay.queries_total | 305.000 | 353.000 | +15.74% |
| backend.query_counts.samples.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.samples.queries_per_request | 11.200 | 13.650 | +21.88% |
| backend.query_counts.samples.queries_total | 224.000 | 273.000 | +21.88% |
| backend.query_counts.session_contents.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.session_contents.queries_per_request | 13.250 | 15.600 | +17.74% |
| backend.query_counts.session_contents.queries_total | 265.000 | 312.000 | +17.74% |
| backend.query_counts.teacher_courses.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.teacher_courses.queries_per_request | 9.250 | 12.500 | +35.14% |
| backend.query_counts.teacher_courses.queries_total | 185.000 | 250.000 | +35.14% |
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
| redis.after.expired_keys | 250.000 | 30.000 | -88.00% |
| redis.after.hit_rate | 0.973 | 0.978 | +0.55% |
| redis.after.instantaneous_ops_per_sec | 894.000 | 293.000 | -67.23% |
| redis.after.keyspace_hits | 8966.000 | 1546.000 | -82.76% |
| redis.after.keyspace_misses | 253.000 | 35.000 | -86.17% |
| redis.after.total_commands_processed | 1902551.000 | 73974.000 | -96.11% |
| redis.before.evicted_keys | 0.000 | 0.000 | - |
| redis.before.expired_keys | 227.000 | 8.000 | -96.48% |
| redis.before.instantaneous_ops_per_sec | 788.000 | 196.000 | -75.13% |
| redis.before.keyspace_hits | 6666.000 | 0.000 | -100.00% |
| redis.before.keyspace_misses | 217.000 | 0.000 | -100.00% |
| redis.before.total_commands_processed | 1728507.000 | 21437.000 | -98.76% |
