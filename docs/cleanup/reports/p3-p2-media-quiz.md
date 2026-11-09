# P3-P2 — Media/quiz/AOI access: bỏ ORM load nặng

- Branch: `cleanup/p3-p2-media-quiz`
- Base: `cleanup/integration`
- Date: 2026-11-09

## Summary

Removed accidental eager loads on the media asset, quiz-spec update, and AOI
slide-access paths without changing API paths, response shapes, status codes,
messages, or auth behavior.

1. **`backend/app/api/routes/media.py`** — `_get_asset_for_user` now loads the
   course with `get_course_or_404` from `app.api.access` instead of
   `db.get(Course, ...)`. That helper already applies
   `raiseload(Course.versions/enrollments/owner/creator)`, so the course graph
   (versions → modules/items, enrollments, owner/creator users) is no longer
   loaded just to check `owner_id`. Missing course still returns 404
   `"Không tìm thấy khóa học"`.
2. **`backend/app/api/routes/quiz_specs.py`** — `update_quiz_spec` now:
   - loads `LessonVersion` with `raiseload(LessonVersion.slides)`;
   - loads `Lesson` with `raiseload(Lesson.versions)` and
     `raiseload(Lesson.slides)`;
   - loads the course with `get_course_or_404` (raiseload course graph).
   Missing lesson still returns 404 `"Không tìm thấy khóa học"`; missing course
   returns the same 404 detail as before.
3. **`backend/app/services/aoi/access.py`** — `_slide_version_course` now:
   - loads `Slide` with `raiseload(Slide.versions)`;
   - loads `Lesson` with `raiseload(Lesson.versions)` and
     `raiseload(Lesson.slides)`;
   - loads `Course` with raiseload for versions/enrollments/owner/creator.
   The combined missing-slide/lesson/course check and its 404 detail
   `"Không tìm thấy khóa học của slide"` are unchanged.
4. **Tests** — added service-level query-count tests using
   `tests.query_counter.count_queries` with real seeded rows:
   - `backend/tests/test_media_access.py`: media asset access for an enrolled
     student and for the course owner, 404 for a missing asset, 403 for an
     outsider, plus `_slide_version_course` query count.
   - `backend/tests/test_quiz_specs_access.py`: quiz-spec update query count
     after the draft course/lesson version already exists (so the measurement
     covers the update path, not the legitimate clone work).

## Query counts (measured)

Measured with `count_queries(engine)` around the service/route function on a
fresh `SessionLocal`, after loading the acting `User` outside the measured
block. "Before" was measured by stashing only the three app-file changes and
running the same tests; the assertion failures reported the actual counts.

| Path | Before | After | Delta |
|---|---:|---:|---:|
| `_get_asset_for_user` — enrolled student | 15 | 4 | −11 |
| `_get_asset_for_user` — course owner | 13 | 2 | −11 |
| `_slide_version_course` — AOI slide access | 20 | 4 | −16 |
| `update_quiz_spec` — update with existing draft | 27 | 12 | −15 |

The media asset budget in `PLAN.md` is ≤ 5 queries; the enrolled-student path
is now 4 and the owner path is 2.

The quiz test also asserts that the measured statements contain no
`lesson_versions_slides`, `FROM slides`, or `FROM enrollments` queries, which
were the accidental selectin loads.

## Files changed

| File | Change |
|---|---|
| `backend/app/api/routes/media.py` | use `get_course_or_404` in `_get_asset_for_user` |
| `backend/app/api/routes/quiz_specs.py` | raiseload on `LessonVersion`/`Lesson`; `get_course_or_404` for course |
| `backend/app/services/aoi/access.py` | raiseload on `Slide`/`Lesson`/`Course` in `_slide_version_course` |
| `backend/tests/test_media_access.py` | new media + AOI access query-count/behavior tests |
| `backend/tests/test_quiz_specs_access.py` | new quiz-spec update query-count test |
| `docs/cleanup/reports/p3-p2-media-quiz.md` | this report |

No forbidden files (`backend/app/models/**`, `backend/app/services/content/**`,
`analysis/**`, `metrics.py`, `course_students.py`, other routes,
`db/migrations/**`, `frontend/**`, `docker-compose.yml`, `README.md`, `.env`)
were modified.

## Tests run

```text
$ backend/.venv/bin/ruff check backend/app backend/tests
All checks passed!

$ TEST_DB=eyetracking_test_p2 ./scripts/test_backend.sh
...
[test_backend] chạy pytest
........................................................                 [100%]
56 passed in 16.13s
[test_backend] OK
```

56 = 50 existing tests + 6 new tests (5 in `test_media_access.py`, 1 in
`test_quiz_specs_access.py`).

### Environment note

The worktree has no `.env` (gitignored, not copied by
`scripts/worktree_setup.sh`). A local untracked copy of the main repo `.env`
was created to run the unmodified test script, and the script was run with
`COMPOSE_PROJECT_NAME=eyelearning` so it targets the already-running stack.
No scripts or tracked config were modified.

## Risks

- **`raiseload` is strict**: any future code that reads
  `course.versions/enrollments/owner/creator`, `lesson.versions/slides`, or
  `slide.versions` on these paths will now raise `InvalidRequestError` instead
  of silently issuing a query. That is intentional (fail fast), but new
  call sites must load those relationships explicitly.
- **Identity-map caveat**: `get_course_or_404` uses `db.get(..., options=...)`.
  If a `Course` is already present in the same session without raiseload, the
  options do not re-apply. Current request-scoped sessions load the course
  fresh on these paths, so behavior is unchanged.
- **AOI detail message**: `_slide_version_course` keeps its own raiseload
  options instead of `get_course_or_404` so the existing 404 detail
  `"Không tìm thấy khóa học của slide"` is preserved exactly.
- **Test coupling**: the exact query counts (4/2/4/12) are deterministic for
  the current SQLAlchemy version and seed data. If the ORM or auth loading
  changes, update the expected counts; the statement-content assertions remain
  the primary regression guard.

## Follow-ups

- `backend/tests/query_counter.py` documents `async with count_queries(...)`
  but implements a synchronous `@contextmanager`; tests must use `with`.
  P4 owns that helper and should fix the docstring or add an async variant.
- Consider reusing `get_course_or_404` in `_slide_version_course` if the
  slide-specific 404 detail is ever allowed to change.
- P4 can add endpoint-level query budgets for the media file route and the
  quiz-spec PATCH once auth/rate-limit noise is normalized.
