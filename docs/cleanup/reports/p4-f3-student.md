# P4-F3 — Student reader / preflight / quiz component split

- Branch: `cleanup/p4-f3-student`
- Base: `cleanup/integration`
- Date: 2026-11-09

## Summary

Split the four large student/reader/quiz components into package directories
without changing behavior, props, or public exports:

1. **`components/student/learning-reader.tsx` (664 lines) → `learning-reader/`**
   - `index.tsx` keeps the `LearningReader` export and `{ courseId }` props.
   - `reader-content.tsx` keeps the session/gaze/AOI orchestration.
   - `reader-banners.tsx` extracts the gaze-disconnected banner.
   - `reader-slide-content.tsx` extracts the PDF/placeholder slide panel.
   - `reader-states.tsx` extracts the loading skeleton and error state.
   - `use-reader-chat.ts` extracts chat open/access/focus state.
   - `reader-helpers.ts` holds pure helpers (`hashPayload`,
     `resolveActiveLessonId`, `getReaderLayoutKey`, `findNextLesson`,
     `isGazeDotVisible`).

2. **`components/student/preflight-check.tsx` (531 lines) → `preflight-check/`**
   - `index.tsx` keeps the `PreflightCheck` export and `{ courseId }` props.
   - `camera-check.tsx` extracts the camera preview panel.
   - `status-panel.tsx` extracts the status rows, errors, and primary action.
   - `no-calibration-view.tsx` extracts the "Vào học ngay" branch.
   - `preflight-header.tsx` extracts the back link + course title.
   - `preflight-types.ts` holds the camera/face/tone unions.
   - `preflight-helpers.ts` holds pure helpers (hrefs, readiness, labels,
     calibration age/description).

3. **`components/reader/reader-frame.tsx` (527 lines) → `reader-frame/`**
   - `index.tsx` keeps the `ReaderFrame` export and the exact same
     `ReaderFrameProps` interface (teacher AOI preview depends on it).
   - `reader-outline.tsx` extracts the module/lesson outline.
   - `reader-topbar.tsx` extracts the header, chat button, gaze badge, and
     mobile outline trigger.
   - `reader-sidebar.tsx` extracts the desktop aside and mobile drawer.
   - `reader-slide-controls.tsx` extracts the prev/next/next-lesson footer.
   - `reader-helpers.ts` holds pure helpers (`allLessons`, `getNextLesson`,
     `isAtLastSlide`, `getGazeStatus`).

4. **`components/quiz/inline-quiz.tsx` (468 lines) → `inline-quiz/`**
   - `index.tsx` keeps the `InlineQuiz` export and `{ quizId, onNext, hasNext }`
     props.
   - `question-view.tsx` extracts the question card and option list.
   - `review-view.tsx` extracts the result/review view and retry dialog.
   - `next-button.tsx` extracts the shared next/end-of-course button.
   - `quiz-helpers.ts` holds pure helpers (percentage, answer matching,
     answered count, remaining minutes, error messages, option letters).

All moved JSX/classes/`data-aoi` attributes were copied verbatim. The only
logic changes are mechanical extractions into pure helpers; the helper tests
pin the original behavior.

## Files changed

### Deleted

| File | Lines |
|---|---|
| `frontend/components/student/learning-reader.tsx` | 664 |
| `frontend/components/student/preflight-check.tsx` | 531 |
| `frontend/components/reader/reader-frame.tsx` | 527 |
| `frontend/components/quiz/inline-quiz.tsx` | 468 |

### Added — `frontend/components/student/learning-reader/`

| File | Lines | Contents |
|---|---:|---|
| `index.tsx` | 12 | `LearningReader` + `AssistantProvider` |
| `reader-content.tsx` | 553 | Session/gaze/AOI orchestration |
| `reader-banners.tsx` | 40 | Gaze-disconnected banner |
| `reader-slide-content.tsx` | 51 | PDF slide / placeholder |
| `reader-states.tsx` | 32 | Loading skeleton + error state |
| `use-reader-chat.ts` | 62 | Chat open/access/focus hook |
| `reader-helpers.ts` | 68 | Pure helpers |
| `reader-helpers.test.ts` | 102 | Vitest coverage |

### Added — `frontend/components/student/preflight-check/`

| File | Lines | Contents |
|---|---:|---|
| `index.tsx` | 294 | `PreflightCheck` state/effects |
| `camera-check.tsx` | 93 | Camera preview panel |
| `status-panel.tsx` | 158 | Status rows + actions |
| `no-calibration-view.tsx` | 39 | No-calibration branch |
| `preflight-header.tsx` | 23 | Back link + course title |
| `preflight-types.ts` | 3 | Camera/face/tone unions |
| `preflight-helpers.ts` | 96 | Pure helpers |
| `preflight-helpers.test.ts` | 144 | Vitest coverage |

### Added — `frontend/components/reader/reader-frame/`

| File | Lines | Contents |
|---|---:|---|
| `index.tsx` | 264 | `ReaderFrame` (props unchanged) |
| `reader-outline.tsx` | 141 | Module/lesson outline |
| `reader-topbar.tsx` | 116 | Header + chat/gaze controls |
| `reader-sidebar.tsx` | 58 | Desktop aside + mobile drawer |
| `reader-slide-controls.tsx` | 65 | Slide navigation footer |
| `reader-helpers.ts` | 28 | Pure helpers |
| `reader-helpers.test.ts` | 70 | Vitest coverage |

### Added — `frontend/components/quiz/inline-quiz/`

| File | Lines | Contents |
|---|---:|---|
| `index.tsx` | 221 | `InlineQuiz` state/effects |
| `question-view.tsx` | 137 | Question card + options |
| `review-view.tsx` | 173 | Review view + retry dialog |
| `next-button.tsx` | 23 | Next/end-of-course button |
| `quiz-helpers.ts` | 61 | Pure helpers |
| `quiz-helpers.test.ts` | 109 | Vitest coverage |

### Added — report

- `docs/cleanup/reports/p4-f3-student.md`

No forbidden files were modified. `git status` only shows the four deleted
component files and the four new package directories plus this report.

> Note: the task card's four-package split produces 29 new source/test files,
> above the plan's 15-file guideline. The file count is inherent to the
> requested directory structure (four packages + helper tests + report); no
> unrelated files were touched.

## Behavior / contract preservation

- `LearningReader`, `PreflightCheck`, `ReaderFrame`, and `InlineQuiz` are still
  named exports from the same import paths (`@/components/.../learning-reader`,
  etc.) via each package `index.tsx`.
- `ReaderFrameProps` is byte-for-byte the same interface as before, including
  `preview`, `interactive`, `gazeSource`, `calibrationRequired`, `banners`,
  `slideContent`, `quizContent`, `chatPanel`, `overlay`, `contentMaxWidth`, and
  `className`.
- `InlineQuiz` props remain `{ quizId, onNext?, hasNext? }`.
- `LearningReader` / `PreflightCheck` props remain `{ courseId }`.
- All `data-aoi` attributes (`reader-root`, `header`, `outline`,
  `lesson-content`, `lesson-nav`, `quiz`, `quiz-question`, `quiz-options`,
  `quiz-submit`, `slide`, `chat-open-button`) are preserved in the same DOM
  positions.
- The teacher AOI preview (`components/teacher/aoi/student-preview.tsx`) still
  imports `ReaderFrame`, `ReaderChatPreview`, and `ReaderQuizPreview` from the
  same paths and compiles unchanged.

## Tests run

All commands were run from `frontend/` in the worktree.

### `npm run lint`

```text
> web@0.1.0 lint
> eslint
```

Pass (no output).

### `npm run typecheck`

```text
> web@0.1.0 typecheck
> tsc --noEmit
```

Pass (no output).

### `npm run test`

```text
> web@0.1.0 test
> vitest run

 Test Files  14 passed (14)
      Tests  151 passed (151)
   Duration  1.83s
```

Baseline was 10 files / 105 tests. Added 4 helper test files / 46 tests.

### `npm run knip`

```text
> web@0.1.0 knip
> knip
```

Pass (no output).

### Extra: production build

`npx next build --webpack` passes (13/13 static pages generated). The default
`npm run build` (Turbopack) fails in this worktree before compiling because
`frontend/node_modules` is a symlink to the main repo outside the worktree
filesystem root:

```text
Symlink [project]/node_modules is invalid, it points out of the filesystem root
```

This is an environment/worktree setup issue, not a code issue; the webpack build
of the same tree succeeds.

## Risks

- **UI behavior is verified by typecheck/build and helper tests, not by
  component-level rendering tests.** The extraction was mechanical and the JSX
  was copied verbatim, but there is no automated DOM snapshot for these four
  components.
- **`reader-content.tsx` is still 553 lines.** The gaze/session/AOI
  orchestration was intentionally left in one place because splitting it would
  require moving many interdependent refs/effects and carries a higher behavior
  risk. Chat state and presentational pieces were extracted instead.
- **Directory-index resolution** relies on Next.js/TypeScript resolving
  `@/components/.../name` to `name/index.tsx`. Typecheck and the webpack build
  confirm this works; the old `.tsx` files were deleted so there is no
  ambiguity.
- **Turbopack build** cannot run in this worktree due to the `node_modules`
  symlink. CI/main-repo builds are unaffected.

## Follow-ups

- Add component-level tests (React Testing Library) for `LearningReader`,
  `PreflightCheck`, `ReaderFrame`, and `InlineQuiz` to lock the rendered
  structure and `data-aoi` contract.
- Consider extracting the gaze/session/AOI orchestration from
  `reader-content.tsx` into a `use-reader-gaze.ts` hook once component tests
  exist to guard the ref/effect lifecycle.
- Fix the worktree setup so `frontend/node_modules` is a real directory (or a
  symlink inside the worktree root) if Turbopack builds are needed per
  worktree.
