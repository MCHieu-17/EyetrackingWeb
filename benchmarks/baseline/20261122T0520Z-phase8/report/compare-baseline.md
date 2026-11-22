# Benchmark comparison

- baseline: `benchmarks/baseline/20261120T180000Z-baseline`
- after: `benchmarks/baseline/20261122T0520Z-phase8`

| Metric | Baseline | After | Delta |
|---|---:|---:|---:|
| backend.query_counts.aoi_summary.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.aoi_summary.queries_per_request | 13.700 | 15.300 | +11.68% |
| backend.query_counts.aoi_summary.queries_total | 274.000 | 306.000 | +11.68% |
| backend.query_counts.course_students.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.course_students.queries_per_request | 12.800 | 11.950 | -6.64% |
| backend.query_counts.course_students.queries_total | 256.000 | 239.000 | -6.64% |
| backend.query_counts.course_visits.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.course_visits.queries_per_request | 9.200 | 10.200 | +10.87% |
| backend.query_counts.course_visits.queries_total | 184.000 | 204.000 | +10.87% |
| backend.query_counts.enrollments.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.enrollments.queries_per_request | 1.500 | 3.850 | +156.67% |
| backend.query_counts.enrollments.queries_total | 30.000 | 77.000 | +156.67% |
| backend.query_counts.outline.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.outline.queries_per_request | 7.300 | 10.000 | +36.99% |
| backend.query_counts.outline.queries_total | 146.000 | 200.000 | +36.99% |
| backend.query_counts.replay.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.replay.queries_per_request | 15.250 | 11.200 | -26.56% |
| backend.query_counts.replay.queries_total | 305.000 | 224.000 | -26.56% |
| backend.query_counts.samples.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.samples.queries_per_request | 11.200 | 10.900 | -2.68% |
| backend.query_counts.samples.queries_total | 224.000 | 218.000 | -2.68% |
| backend.query_counts.session_contents.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.session_contents.queries_per_request | 13.250 | 11.900 | -10.19% |
| backend.query_counts.session_contents.queries_total | 265.000 | 238.000 | -10.19% |
| backend.query_counts.teacher_courses.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.teacher_courses.queries_per_request | 9.250 | 8.650 | -6.49% |
| backend.query_counts.teacher_courses.queries_total | 185.000 | 173.000 | -6.49% |
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
| redis.after.expired_keys | 250.000 | 69.000 | -72.40% |
| redis.after.hit_rate | 0.973 | 0.976 | +0.35% |
| redis.after.instantaneous_ops_per_sec | 894.000 | 100.000 | -88.81% |
| redis.after.keyspace_hits | 8966.000 | 3573.000 | -60.15% |
| redis.after.keyspace_misses | 253.000 | 88.000 | -65.22% |
| redis.after.total_commands_processed | 1902551.000 | 20617.000 | -98.92% |
| redis.before.evicted_keys | 0.000 | 0.000 | - |
| redis.before.expired_keys | 227.000 | 36.000 | -84.14% |
| redis.before.hit_rate | 0.968 | 0.972 | +0.32% |
| redis.before.instantaneous_ops_per_sec | 788.000 | 0.000 | -100.00% |
| redis.before.keyspace_hits | 6666.000 | 1263.000 | -81.05% |
| redis.before.keyspace_misses | 217.000 | 37.000 | -82.95% |
| redis.before.total_commands_processed | 1728507.000 | 1939.000 | -99.89% |
