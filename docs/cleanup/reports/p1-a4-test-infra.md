# P1-A4 — Test/quality gate foundation

- Branch: `cleanup/p1-a4-test-infra`
- Base: `cleanup/integration`
- Scope: test/quality infrastructure only; no application behavior changed.

## Summary

- `scripts/check.sh` now supports `--full` (ruff, lint, typecheck, knip, frontend
  unit tests, backend tests, build, compose config) while keeping the default
  gate and `--build` behavior unchanged.
- Added a root `Makefile` with the standard check/test/build/stack targets.
- Added Vitest coverage for pure frontend logic:
  - AOI rect measurement + `aoiRectsKey` stability.
  - Calibration geometry (margins, 5×5 grid, gaze transform).
  - Quiz validation (`questionIssues`, `isQuestionComplete`, `trimQuestion`,
    `draftPayload`).
  - Chat markdown helpers (`normalizeMath`, `remarkCitations`).
- Added `backend/tests/query_counter.py`, a reusable SQLAlchemy event-based
  query counter for the Phase 3/P4 performance work. No existing test changed.

## Files changed

| File | Change |
|---|---|
| `scripts/check.sh` | Added `--full`, kept default and `--build`; clearer logs and arg validation. |
| `Makefile` | New targets: `check`, `check-full`, `test-backend`, `test-frontend`, `build`, `up`, `down`, `smoke`. |
| `frontend/lib/aoi/measure.test.ts` | New: 12 tests for `measureAoiRects` / `aoiRectsKey`, including a DOM-update case. |
| `frontend/lib/calibration-geometry.test.ts` | New: 13 tests for margins, grid generation, gaze transform. |
| `frontend/lib/quiz-validation.test.ts` | New: 14 tests for validation/trim/draft payload. |
| `frontend/lib/chat-markdown.test.ts` | New: 11 tests for math normalization and citation links. |
| `backend/tests/query_counter.py` | New optional helper: `count_queries(engine)` context manager + `QueryCounter`. |

No forbidden files were modified (`frontend/package.json`,
`frontend/package-lock.json`, `frontend/vitest.config.ts`,
`frontend/vitest.setup.ts`, `frontend/lib/utils.test.ts`,
`frontend/lib/api/client.test.ts`, app/component/hook/API code, migrations,
compose, README, `.env`).

## Tests run

| Command | Result |
|---|---|
| `cd frontend && npm run test` | **4 files, 50 tests passed** (~0.8s) |
| `cd frontend && npm run lint` | pass |
| `cd frontend && npm run typecheck` | pass |
| `cd frontend && npm run knip` | pass |
| `./scripts/check.sh` | pass (`[check] OK`) |
| `./scripts/check.sh --full` | pass (`[check] OK`) |

`--full` highlights: ruff `All checks passed!`; frontend 4 files / 50 tests
passed; backend `28 passed in 12.68s`; Next build compiled and generated all
13 static pages; compose config OK.

## Environment notes

- The worktree had no `.env`, required by `scripts/test_backend.sh`. For the
  `--full` run only, a temporary symlink to the main repo `.env` was used and
  removed afterwards; `COMPOSE_PROJECT_NAME=eyelearning` reused the running
  stack. Nothing was committed.
- The worktree `frontend/node_modules` symlink is outside the Turbopack root,
  which makes `next build` fail. A local `npm ci` install was used for build
  verification (untracked/ignored); this is a worktree-setup limitation.
- `knip` flagged `@testing-library/react` and `@testing-library/user-event` as
  unused. Since `package.json`/`knip.json` are outside this task's ownership,
  `measure.test.ts` uses both in a real DOM-update test instead of suppressing
  them.

## Risks

- `./scripts/check.sh --full` is not self-contained: it needs `.env`, a running
  Postgres/compose stack, and a real (non-symlinked) `frontend/node_modules` for
  the Turbopack build. CI should provide these.
- Backend tests create/drop the `eyetracking_test` database; do not point
  `TEST_DB` at a database with real data.
- `query_counter.py` is intentionally untested until P4 wires it into
  performance tests; it only listens to SQLAlchemy events and does not alter
  query behavior.
- Vitest prints a pre-existing Vite ESM/CommonJS warning; it does not fail.

## Follow-ups

- P4: use `backend/tests/query_counter.py` to assert the query budgets in
  `docs/cleanup/PLAN.md` (gaze batch ≤ 5, course list ≤ 10, etc.).
- Phase 4: add Playwright E2E and decide whether it belongs in `--full` or a
  separate `check-e2e` target.
- Worktree setup: prefer a real `npm ci` (or configure Turbopack root) instead
  of symlinking `frontend/node_modules`, otherwise `next build` fails in
  worktrees.
