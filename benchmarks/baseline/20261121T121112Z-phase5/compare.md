# Benchmark comparison

- baseline: `benchmarks/baseline/20261120T180000Z-baseline`
- after: `benchmarks/baseline/20261121T121112Z-phase5`

| Metric | Baseline | After | Delta |
|---|---:|---:|---:|
| backend.query_counts.aoi_summary.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.aoi_summary.queries_per_request | 13.700 | 15.650 | +14.23% |
| backend.query_counts.aoi_summary.queries_total | 274.000 | 313.000 | +14.23% |
| backend.query_counts.course_students.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.course_students.queries_per_request | 12.800 | 14.500 | +13.28% |
| backend.query_counts.course_students.queries_total | 256.000 | 290.000 | +13.28% |
| backend.query_counts.course_visits.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.course_visits.queries_per_request | 9.200 | 12.200 | +32.61% |
| backend.query_counts.course_visits.queries_total | 184.000 | 244.000 | +32.61% |
| backend.query_counts.enrollments.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.enrollments.queries_per_request | 1.500 | 4.200 | +180.00% |
| backend.query_counts.enrollments.queries_total | 30.000 | 84.000 | +180.00% |
| backend.query_counts.outline.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.outline.queries_per_request | 7.300 | 9.700 | +32.88% |
| backend.query_counts.outline.queries_total | 146.000 | 194.000 | +32.88% |
| backend.query_counts.replay.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.replay.queries_per_request | 15.250 | 17.200 | +12.79% |
| backend.query_counts.replay.queries_total | 305.000 | 344.000 | +12.79% |
| backend.query_counts.samples.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.samples.queries_per_request | 11.200 | 13.900 | +24.11% |
| backend.query_counts.samples.queries_total | 224.000 | 278.000 | +24.11% |
| backend.query_counts.session_contents.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.session_contents.queries_per_request | 13.250 | 15.900 | +20.00% |
| backend.query_counts.session_contents.queries_total | 265.000 | 318.000 | +20.00% |
| backend.query_counts.teacher_courses.iterations | 20.000 | 20.000 | +0.00% |
| backend.query_counts.teacher_courses.queries_per_request | 9.250 | 11.600 | +25.41% |
| backend.query_counts.teacher_courses.queries_total | 185.000 | 232.000 | +25.41% |
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
| redis.after.expired_keys | 250.000 | 261.000 | +4.40% |
| redis.after.hit_rate | 0.973 | 0.976 | +0.33% |
| redis.after.instantaneous_ops_per_sec | 894.000 | 297.000 | -66.78% |
| redis.after.keyspace_hits | 8966.000 | 7244.000 | -19.21% |
| redis.after.keyspace_misses | 253.000 | 180.000 | -28.85% |
| redis.after.total_commands_processed | 1902551.000 | 172599.000 | -90.93% |
| redis.before.evicted_keys | 0.000 | 0.000 | - |
| redis.before.expired_keys | 227.000 | 239.000 | +5.29% |
| redis.before.hit_rate | 0.968 | 0.972 | +0.33% |
| redis.before.instantaneous_ops_per_sec | 788.000 | 196.000 | -75.13% |
| redis.before.keyspace_hits | 6666.000 | 4905.000 | -26.42% |
| redis.before.keyspace_misses | 217.000 | 143.000 | -34.10% |
| redis.before.total_commands_processed | 1728507.000 | 119256.000 | -93.10% |
