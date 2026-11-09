# P1-A3 — Chatbot history dedup + knip config

## Summary

- Moved the duplicated `_history_messages()` helper out of
  `services/chatbot/app/workflow/router.py` and
  `services/chatbot/app/workflow/answer.py` into a new shared module,
  `services/chatbot/app/workflow/history.py`.
- Moved `budget_history()` into the same module as well. Keeping it in
  `router.py` and importing it from `history.py` would have created a circular
  import (`router` → `history` → `router`). `router.py` now imports both helpers
  from `history.py`.
- Behavior is unchanged: same last-10-items / 16,000-character budget, same
  `student` → `HumanMessage` / other → `AIMessage` mapping, same stripping and
  empty-content filtering. No prompt text, model name, or retrieval logic was
  touched.
- Added `services/chatbot/tests/test_history.py` with two small tests covering
  role mapping, empty-content filtering, and the history budget.
- `frontend/knip.json` was intentionally **not** changed. The `"mdast"` entry is
  not stale in this tree; removing it makes `npx knip` fail. Details in
  "Knip finding" below.

## Files changed

| File | Change |
|---|---|
| `services/chatbot/app/workflow/history.py` | New shared module with `budget_history()` and `_history_messages()` |
| `services/chatbot/app/workflow/router.py` | Removed local copies; imports helpers from `history.py` |
| `services/chatbot/app/workflow/answer.py` | Removed local copy; imports `_history_messages` from `history.py` |
| `services/chatbot/tests/test_history.py` | New tests for role mapping, empty filtering, and budget behavior |
| `docs/cleanup/reports/p1-a3-chatbot-dedup.md` | This report |
| `frontend/knip.json` | Unchanged — see "Knip finding" |

No forbidden files were modified.

## Tests run

All commands were run from the worktree root unless noted.

### `ruff check services/chatbot/app`

```text
All checks passed!
```

Also ran `ruff check services/chatbot` (includes the new test file):

```text
All checks passed!
```

### `python -m compileall -q services/chatbot/app`

```text
compileall: OK
```

### `cd services/chatbot && <repo-chatbot-venv>/bin/python -m pytest -q tests/test_history.py`

```text
..                                                                       [100%]
2 passed in 0.03s
```

Notes:

- The worktree has no `services/chatbot/.venv`. The repo's existing chatbot venv
  was used read-only:
  `/home/hieu/Documents/NCKH Eyetracking/EyeLearning/services/chatbot/.venv`
  (pytest 9.1.1, langchain_core 1.6.12).
- `python -m pytest` is used instead of the bare `pytest` entrypoint because the
  service root is not on `sys.path` when the entrypoint is invoked directly
  (`ModuleNotFoundError: No module named 'app'`). This is a pre-existing
  packaging gap, not caused by this change.
- `services/chatbot/requirements-dev.txt` currently only pins `ruff`; it does not
  declare `pytest`. The test was added because pytest is available in the repo's
  chatbot venv, but it is not wired into CI yet (see follow-ups).

### `cd frontend && npx knip`

```text
Unused devDependencies (2)
@testing-library/react       package.json:53:6
@testing-library/user-event  package.json:54:6
EXIT=1
```

This failure is pre-existing on `cleanup/integration`: A4 added the Vitest /
Testing Library dependencies before the test files were committed. It is not
caused by this task. Verified by temporarily copying A4's four test files into
this worktree and re-running knip: `npx knip` exited `0` with the existing
`mdast` ignore in place. The copied files were removed afterwards.

### Ad-hoc behavior check

Ran a small script with the repo chatbot venv against the new module:

- `student` → `HumanMessage`, `assistant` → `AIMessage`
- whitespace-only and empty content skipped
- content stripped
- `budget_history` keeps the most recent items within the character budget, in
  original order
- `app.workflow.router` and `app.workflow.answer` import successfully and both
  reference the same `_history_messages` object

## Knip finding (task 2 blocked by ownership)

`frontend/knip.json` still contains:

```json
{
  "ignoreDependencies": ["mdast"]
}
```

The entry is **not stale** in this tree:

- `frontend/lib/chat-markdown.ts:1` contains
  `import type { Root, Text, Link } from "mdast";`.
- `mdast` is not declared in `frontend/package.json`.
- `@types/mdast@4.0.4` is present only as a transitive dependency.
- Removing the ignore produces:

  ```text
  Unlisted dependencies (1)
  mdast  lib/chat-markdown.ts:1:39
  ```

The correct fix is outside A3 ownership: add `@types/mdast` to
`frontend/package.json` `devDependencies` (A4 owns `package.json`), then remove
the `"mdast"` ignore. Knip maps `@types/mdast` to the type-only `mdast` import,
so the ignore becomes unnecessary. I did not edit `package.json` or
`chat-markdown.ts`.

## Risks

- Low. The refactor is a pure move of two pure functions; no prompt, model,
  retrieval, or API behavior changed.
- `_history_messages` is still private by name but is now imported by two
  modules. If it becomes a public helper, rename it to `history_messages` in a
  follow-up.
- The new test file is not part of the current CI gate because
  `requirements-dev.txt` does not declare pytest and the service has no pytest
  path configuration.

## Follow-ups

1. **A4 / frontend owner:** add `@types/mdast` to `frontend/package.json`
   `devDependencies`, then remove `"mdast"` from `frontend/knip.json`
   `ignoreDependencies` and re-run `npx knip`.
2. **A4:** commit the Vitest test files so `@testing-library/react` and
   `@testing-library/user-event` are used and knip stops reporting them as
   unused.
3. **Chatbot owner:** add `pytest` to `services/chatbot/requirements-dev.txt`
   and a pytest config (for example `pythonpath = .`) so
   `pytest tests/test_history.py` works without `python -m`.
4. Optional: rename `_history_messages` to `history_messages` if it should be a
   supported cross-module helper.
