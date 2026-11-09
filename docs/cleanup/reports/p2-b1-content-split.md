# P2-B1 — Split `services/content.py` into a package

- Branch: `cleanup/p2-b1-content-split`
- Base: `cleanup/integration`
- Date: 2026-11-09

## Summary

Split the 1,844-line `backend/app/services/content.py` god module into the
package `backend/app/services/content/` without changing behavior, SQL,
response shapes, or public imports.

- `from app.services import content` still resolves to the package and exposes
  every public function that was previously importable.
- `from app.services.content import process_pending_slide_imports` (used by
  `backend/app/content_worker.py`) still works.
- All route modules (`courses`, `lessons`, `modules`, `module_items`,
  `quiz_specs`, `quiz_attempts`, `learning_sessions`) were left untouched and
  keep working through the package `__init__.py` re-exports.
- Function bodies were copied verbatim. An AST comparison of every top-level
  function against the original module found no missing/extra functions and
  exactly one body difference: `get_draft_version` now imports
  `clone_course_version` lazily inside the function to avoid a
  `common` ↔ `versions` import cycle. No logic changed.

## Package layout

| Module | Contents |
|---|---|
| `content/__init__.py` | Explicit re-exports + `__all__` (35 public functions + `logger`) |
| `content/common.py` | `_now`, `_conflict`, `_not_found`, `get_course_or_404`, `get_published_version`, `get_draft_version`, `bump_generation`, `check_generation`, shared `logger` |
| `content/versions.py` | `clone_course_version`, `clone_lesson_version`, `ensure_draft_lesson_version` |
| `content/courses.py` | `list_teacher_courses`, `create_course`, `update_course_metadata`, `delete_course` |
| `content/modules.py` | `course_of_module`, `_draft_module`, `_next_module_position`, `create_module`, `update_module`, `delete_module` |
| `content/lessons.py` | `get_draft_item_for_lesson`, `_draft_item`, `_next_item_position`, `_renumber_items`, `create_lesson`, `create_quiz_item`, `update_lesson`, `delete_lesson`, `reorder_items` |
| `content/slides.py` | `_sha256`, `_asset_for_bytes`, `create_slide_import`, `get_slide_import_job`, `process_slide_import`, `process_pending_slide_imports`, `list_lesson_slides_admin`, `_slide_out`, `_slide_rows`, `get_lesson_version_contents`, `get_lesson_contents` |
| `content/publish.py` | `_validate_questions`, `validate_draft`, `publish_course`, `published_quiz_lesson_ids` |
| `content/outline.py` | `_outline_item_rows`, `get_draft_tree`, `get_published_outline` |
| `content/students.py` | `get_course_students` |

Dependency direction is one-way (`common` ← `versions` ← `lessons` ← `slides`,
`common` ← `publish` ← `outline`). The only cycle risk (`common.get_draft_version`
→ `versions.clone_course_version`) is handled with a function-local import.

## Files changed

| File | Change |
|---|---|
| `backend/app/services/content.py` | Deleted (1,844 lines) |
| `backend/app/services/content/__init__.py` | New — public re-exports + `__all__` |
| `backend/app/services/content/common.py` | New |
| `backend/app/services/content/versions.py` | New |
| `backend/app/services/content/courses.py` | New |
| `backend/app/services/content/modules.py` | New |
| `backend/app/services/content/lessons.py` | New |
| `backend/app/services/content/slides.py` | New |
| `backend/app/services/content/publish.py` | New |
| `backend/app/services/content/outline.py` | New |
| `backend/app/services/content/students.py` | New |
| `backend/tests/test_content_imports.py` | New — import/contract test |
| `docs/cleanup/reports/p2-b1-content-split.md` | This report |

No forbidden files (`analysis.py`, `aoi.py`, `metrics.py`, `embedding.py`,
`media_storage.py`, `slide_aoi.py`, `slide_import.py`, `api/**`, `models/**`,
`db/migrations/**`, `frontend/**`, `docker-compose.yml`, `README.md`, `.env`)
were modified.

## Tests run

```text
$ backend/.venv/bin/ruff check backend/app backend/tests
All checks passed!

$ TEST_DB=eyetracking_test_b1 COMPOSE_PROJECT_NAME=eyelearning ./scripts/test_backend.sh
...
[test_backend] chạy pytest
.....................................                                    [100%]
37 passed in 13.79s
[test_backend] OK
```

37 = 34 existing tests + 3 new tests in `test_content_imports.py`:

1. `from app.services import content` returns the package.
2. `from app.services.content import process_pending_slide_imports` is callable.
3. All 35 public callables exist and are listed in `content.__all__`.

### Environment note

The worktree has no `.env` (gitignored, not copied by
`scripts/worktree_setup.sh`). A local untracked symlink
`.env -> ../../EyeLearning/.env` was created to run the unmodified test script,
and `COMPOSE_PROJECT_NAME=eyelearning` was used so `docker compose exec/run`
targets the already-running stack instead of creating a new compose project.
No scripts or tracked config were modified.

## Risks

- **Import cycle regression**: `common.get_draft_version` uses a function-local
  import of `versions.clone_course_version`. If future code moves that call to
  module scope, the package will fail to import. The new import test catches
  package-level import breakage.
- **`__all__` drift**: new public functions added to submodules must be added to
  `content/__init__.py`; otherwise `from app.services import content` will not
  expose them. The contract test only covers the current public surface.
- **Logger name**: preserved as `app.services.content` (not
  `app.services.content.common`) so log routing/filters keep working.
- **Private cross-module helpers**: `_draft_item`, `_draft_module`,
  `_slide_rows`, etc. are imported across submodules. They remain private by
  convention but are now package-internal API; renaming them requires updating
  the sibling modules.

## Follow-ups

- Consider adding a lint rule or test that asserts every public function in
  `content/*.py` is re-exported from `content/__init__.py`.
- The package is still large (~2.1k lines including the test). A later pass
  could split `slides.py` (508 lines) into import-job and slide-read modules if
  it keeps growing.
- No behavior/SQL changes were made, so no performance or API follow-up is
  required from this task.
