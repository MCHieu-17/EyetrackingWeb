# P1-A2 — Frontend API/client dedup + date/query-key cleanup

- Branch: `cleanup/p1-a2-frontend-api`
- Base: `cleanup/integration` (`1db3605`)
- Date: 2026-11-09

## Summary

- Gom logic CSRF và refresh/retry 401 trong `lib/api/client.ts`:
  - `readCsrfToken()` dùng chung cho `getCsrfHeader` và `tryRefresh`.
  - `fetchWithAuthRetry()` dùng chung cho `apiFetch` và `apiFetchMultipart`.
  - `parseApiError()` đọc `detail`/`message` và `Retry-After`, dùng chung với chat.
- Bỏ `toApiError` cục bộ trong `lib/api/chat.ts`, dùng `parseApiError`.
- `fetchTeacherCourses` trả raw `updatedAt`; format `dd/MM/yyyy` tại render trong
  `teacher-course-list.tsx`.
- Thêm `formatDateVN` / `formatDateTimeVN` vào `lib/utils.ts`; thay 4 bản
  `formatDate` cục bộ ở admin/profile/course-browser/preflight.
- Thêm `lib/query-keys.ts` và chuyển các hook được giao sang dùng factory.
- Tách `lib/api/calibration.ts` thành:
  - `calibration-session.ts`: localStorage/session + screen snapshot.
  - `calibration-api.ts`: HTTP `/gaze/*` và `/api/calibrations`.
  - `calibration.ts` giữ vai trò facade, re-export toàn bộ public symbol cũ.
- Thêm Vitest cho utils, `parseApiError`/`readCsrfToken`, query keys.

## Files changed

Modified:

- `frontend/lib/api/client.ts`
- `frontend/lib/api/chat.ts`
- `frontend/lib/api/teacher.ts`
- `frontend/lib/api/calibration.ts` (facade)
- `frontend/lib/utils.ts`
- `frontend/hooks/use-admin.ts`
- `frontend/hooks/use-teacher.ts`
- `frontend/hooks/use-student.ts`
- `frontend/hooks/use-quiz.ts`
- `frontend/hooks/use-chat.ts`
- `frontend/hooks/use-profile.ts`
- `frontend/hooks/use-stored-user.ts`
- `frontend/hooks/use-course-status.ts`
- `frontend/components/teacher/teacher-course-list.tsx`
- `frontend/components/admin/student-promotion.tsx`
- `frontend/components/profile/profile-page.tsx`
- `frontend/components/courses/course-browser.tsx`
- `frontend/components/student/preflight-check.tsx`

Added:

- `frontend/lib/api/calibration-session.ts`
- `frontend/lib/api/calibration-api.ts`
- `frontend/lib/query-keys.ts`
- `frontend/lib/utils.test.ts`
- `frontend/lib/api/client.test.ts`
- `frontend/lib/query-keys.test.ts`
- `docs/cleanup/reports/p1-a2-frontend-api.md`

No forbidden files changed (`frontend/lib/types/domain.ts`, `components/ui/**`,
`package.json`, `package-lock.json`, `app/layout.tsx`, backend, migrations,
docker-compose, README, `.env`).

## Tests run

```text
cd frontend
npm run lint       # pass (eslint, no output)
npm run typecheck  # pass (tsc --noEmit, no output)
npm run test       # pass: 3 files, 23 tests
npm run knip       # pass (no unused files/exports/dependencies)
```

Vitest output:

```text
Test Files  3 passed (3)
     Tests  23 passed (23)
  Duration  1.07s
```

Coverage added:

- `utils.test.ts`: `formatDateVN` (ISO date-only, ISO timestamp, Intl fallback,
  invalid/missing), `formatDateTimeVN`, `formatShortDate`, `initialsOf`.
- `client.test.ts`: `parseApiError` with string/object `detail`, `message`
  fallback, non-JSON body, `Retry-After` valid/invalid; `readCsrfToken` cookie
  decode/missing.
- `query-keys.test.ts`: stable arrays for admin/teacher/student/quiz/chat/
  profile/auth keys.

## Diff size

`git diff --cached --stat` (including new files):

```text
25 files changed, 1018 insertions(+), 578 deletions(-)
```

This exceeds the 15-file / 800-LOC guideline. The overage is structural, not
new behavior: the required calibration split moves ~420 lines into two new
files (`calibration-api.ts` 313, `calibration-session.ts` 101) and the task
also requires three new test files plus this report. Net production logic is
unchanged; the large deletion is the old `calibration.ts` body.

## Risks

- `apiFetch` errors now include `retryAfter` when the backend sends
  `Retry-After` (additive; previously only chat errors had it).
- `formatDateVN` uses the `YYYY-MM-DD` prefix for ISO timestamps to avoid
  timezone/SSR date shifts. For admin/profile timestamps this can differ by one
  day from the old `Intl` output when the timestamp is near midnight UTC; this
  is intentional and deterministic.
- Query key contents are unchanged; only construction moved to factories.
  `*Root` keys preserve prefix invalidation behavior.
- Calibration facade keeps all public exports, so existing imports in hooks and
  components are untouched. `calibration-api.ts` keeps dynamic `./client`
  imports to avoid eagerly loading the client module.
- `knip` initially flagged `@testing-library/react` and
  `@testing-library/user-event` (added by A4, unused at this base). A small DOM
  smoke test in `utils.test.ts` exercises both; no package/knip config change.

## Follow-ups

- Update remaining components that still build raw query keys
  (`components/teacher/**`, `components/account/**`) to use `queryKeys` in a
  later frontend task; this task intentionally limited changes to hooks.
- Consider moving `MY_PROFILE_QUERY_KEY` / `AUTH_USER_QUERY_KEY` ownership fully
  into `lib/query-keys.ts` once `lib/api/profile.ts` and
  `hooks/use-stored-user.ts` consumers are migrated.
- Add tests for `fetchWithAuthRetry` (401 refresh/retry) with mocked `fetch` if
  the auth flow changes.
