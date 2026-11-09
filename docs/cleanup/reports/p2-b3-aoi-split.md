# P2-B3 — AOI package split + course_students extraction

## Summary

- Split `backend/app/services/aoi.py` (851 lines) into the package
  `backend/app/services/aoi/` with no logic, SQL, response-shape, or signature
  changes.
- Moved `course_students` from `backend/app/services/metrics.py` to
  `backend/app/services/course_students.py`.
- Kept `metrics.course_students` as a thin async wrapper delegating to
  `course_students.course_students`, so `content.get_course_students` and any
  other caller keep working.
- Added `backend/tests/test_aoi_imports.py` covering the package exports and the
  metrics wrapper.
- Verified every moved function body is byte-for-byte identical to the original
  (AST source comparison of all 34 AOI functions and `course_students`).

## Package layout

```text
backend/app/services/aoi/
├── __init__.py      # public re-exports + module docstring
├── common.py        # NO_LABEL_* constants, _now/_not_found/_bad_request/_conflict
├── access.py        # _slide_version_course, _require_slide_access/_manage,
│                    # published_aoi_set, _latest_set_for_slide/_ui
├── definitions.py   # serialization, validation, _definitions,
│                    # _insert_definitions, ensure_no_label_definition,
│                    # _replace_definitions
├── sets.py          # list_aoi_sets, _next_revision, _publish_draft,
│                    # _clone_to_draft, save_slide_aoi_set, save_ui_aoi_set
└── generate.py      # slide/UI generation helpers + generate_*_aoi_set
```

`common.py` is an addition to the suggested layout: it holds the four shared
HTTP helpers and the `no_label` constants so `access`, `definitions`, `sets`,
and `generate` do not need to import each other for them. Dependency direction
is acyclic: `common` → `definitions` → `sets` → `generate`, with `access`
independent of `definitions`/`sets`.

Public names re-exported from `app.services.aoi`:

- `list_aoi_sets`
- `generate_slide_aoi_set`
- `save_slide_aoi_set`
- `generate_ui_aoi_set`
- `save_ui_aoi_set`
- `published_aoi_set`
- `ensure_no_label_definition`
- `NO_LABEL_CODE`, `NO_LABEL_NAME`, `AUTO_KINDS`

`gaze_ingest.py` continues to use `from app.services import aoi as aoi_service`
and `aoi_service.published_aoi_set(...)`.

## Files changed

| File | Change |
|---|---|
| `backend/app/services/aoi.py` | Deleted (replaced by package) |
| `backend/app/services/aoi/__init__.py` | New — public re-exports |
| `backend/app/services/aoi/common.py` | New — shared helpers/constants |
| `backend/app/services/aoi/access.py` | New — access checks + lookups |
| `backend/app/services/aoi/definitions.py` | New — definition helpers |
| `backend/app/services/aoi/sets.py` | New — list/save/publish flows |
| `backend/app/services/aoi/generate.py` | New — generation flows |
| `backend/app/services/course_students.py` | New — moved `course_students` + `DEFAULT_ALGORITHM_VERSION` |
| `backend/app/services/metrics.py` | Removed moved code; thin wrapper + re-export |
| `backend/tests/test_aoi_imports.py` | New — import contract tests |
| `docs/cleanup/reports/p2-b3-aoi-split.md` | New — this report |

No forbidden files were modified.

## Behavior preservation

- All 34 functions from the old `aoi.py` were compared with
  `ast.get_source_segment` against the new package; every body matched exactly.
- `compute_presentation_metrics` and `refresh_session_metrics` bodies matched
  exactly.
- The moved `course_students` body matched exactly.
- `DEFAULT_ALGORITHM_VERSION` moved to `course_students.py` and is re-exported
  from `metrics.py`, so `metrics.DEFAULT_ALGORITHM_VERSION` still resolves.
- `metrics.__all__` documents the retained public surface.

## Tests run

```text
$ backend/.venv/bin/ruff check backend/app backend/tests
All checks passed!

$ COMPOSE_PROJECT_NAME=eyelearning TEST_DB=eyetracking_test_b3 ./scripts/test_backend.sh
...
......................................                                   [100%]
38 passed in 14.00s
[test_backend] OK
```

`38 passed` = 34 pre-existing tests + 4 new import-contract tests.

Environment note: the worktree has no `.env` and its compose project name
differs from the running stack, so the test run used a copy of the main repo's
gitignored `.env` and `COMPOSE_PROJECT_NAME=eyelearning`. No tracked file was
affected.

## Risks

- Low: pure module move; function bodies and SQL are unchanged.
- Private helpers (`_definitions`, `_publish_draft`, etc.) are no longer
  importable directly from `app.services.aoi`; no current caller imports them.
  They remain available from their submodules.
- `DEFAULT_ALGORITHM_VERSION` now lives in `course_students.py`; `metrics`
  re-exports it, so existing imports keep working.
- Import order is now `metrics` → `course_students`; `course_students` does not
  import `metrics`, so there is no cycle.

## Follow-ups

- Phase 3 (P2/P3) can now target the smaller `aoi/access.py` and
  `course_students.py` modules for query-count work.
- If future code needs private AOI helpers, import them from the owning
  submodule rather than re-adding them to `__init__.py`.
