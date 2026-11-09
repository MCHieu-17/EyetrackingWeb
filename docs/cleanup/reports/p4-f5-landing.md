# P4-F5 — Landing page server split + Geist Mono removal

- Branch: `cleanup/p4-f5-landing`
- Base: `cleanup/integration` (`325bdb8`)
- Date: 2026-11-09

## Summary

- Converted `frontend/components/landing/landing-v2.tsx` from a full client
  component to a server component (removed `"use client"`).
- Extracted only the interactive state into two client islands:
  - `landing-header.tsx`: mobile menu state, nav links, login/CTA buttons.
  - `landing-role-tabs.tsx`: role tab state and role detail panel.
- Kept all static sections and illustrations in `landing-v2.tsx` as server
  components. `LandingV2` remains the default export.
- Added `landing-arrow.tsx`, a tiny shared `Arrow` component used by both the
  server sections and the client islands (avoids duplicating the icon markup).
- Removed `Geist_Mono` from `frontend/app/layout.tsx`; Inter and Geist are
  unchanged.
- Added a system monospace stack for `--font-mono` in `:root` in
  `frontend/app/globals.css`, so the existing `font-mono` utility still works.
- No copy, layout, CSS class, or rendered DOM changes. The rendered landing
  markup (`<div class="ge-page">…</footer></div>`) is byte-for-byte identical
  before/after (see verification below).

## Files changed

Modified:

- `frontend/components/landing/landing-v2.tsx`
- `frontend/app/layout.tsx`
- `frontend/app/globals.css`

Added:

- `frontend/components/landing/landing-header.tsx`
- `frontend/components/landing/landing-role-tabs.tsx`
- `frontend/components/landing/landing-arrow.tsx`
- `docs/cleanup/reports/p4-f5-landing.md`

No forbidden files changed (`frontend/components/ui/**`,
`frontend/components/account/**`, `frontend/components/layout/**`,
`frontend/lib/**`, `frontend/hooks/**`, `frontend/package.json`,
`frontend/package-lock.json`, backend, migrations, compose, README, `.env`).
`frontend/app/page.tsx` did not need changes; it already imports the default
`LandingV2` export.

Diff size (source changes, excluding this report):

```text
6 files changed, 153 insertions(+), 124 deletions(-)
```

## Tests run

```text
cd frontend
npm run lint       # pass (eslint, no output)
npm run typecheck  # pass (tsc --noEmit, no output)
npm run test       # pass: 7 files, 73 tests
npm run knip       # pass (no unused files/exports/dependencies)
npm run build      # pass (Next.js 16.3.1 Turbopack)
```

Vitest output:

```text
Test Files  7 passed (7)
     Tests  73 passed (73)
  Duration  1.63s
```

Build output (Turbopack):

```text
✓ Compiled successfully in 3.8s
  Running TypeScript ...
✓ Generating static pages using 11 workers (13/13)
```

### Worktree build note

The worktree setup symlinks `frontend/node_modules` to the main repo, which is
outside the Turbopack root. Plain `npm run build` therefore fails in a fresh
worktree with:

```text
Symlink [project]/node_modules is invalid, it points out of the filesystem root
```

For verification, a local `npm ci` was run in this worktree (untracked/ignored,
same lockfile), after which plain `npm run build` passed. This is the same
worktree limitation documented in `p1-a4-test-infra.md`; it is not caused by
this change. The webpack build (`npm run build -- --webpack`) also passes with
the symlinked `node_modules`.

## Bundle notes

Measured from the static `/` HTML script tags and the emitted chunk files. The
before/after comparison uses webpack for both sides (same bundler, same
environment), so it is directly comparable.

| Metric | Before | After | Delta |
|---|---|---|---|
| Initial JS `/` (raw) | 722,459 B (705.5 KB) | 708,967 B (692.4 KB) | −13,492 B (−1.9%) |
| Landing page chunk `app/page-*.js` | 19,276 B | 5,986 B | −13,290 B (−69.0%) |
| Global CSS | 89,838 B | 87,956 B | −1,882 B (−2.1%) |
| Font preloads on `/` | 4 (Inter ×2, Geist, Geist Mono) | 3 (Inter ×2, Geist) | −1 Geist Mono woff2 |

The remaining initial JS is framework/shared chunks (React, Next runtime,
polyfills, shared UI); the landing-specific client chunk now contains only the
two islands (`LandingHeader`, `LandingRoleTabs`, `ge-mobile-panel`,
`ge-role-tabs-wrap`) and no static illustration markup (`ge-hero-art` is absent
from the client chunk).

Turbopack build after the change (for reference, not directly comparable to the
webpack baseline): initial JS `/` = 725,290 B raw (708.3 KB), 223,797 B gzip
(218.6 KB).

## DOM verification

Extracted the rendered `<div class="ge-page">…</footer></div>` block from the
baseline build HTML and the new build HTML (both webpack and Turbopack builds
were checked). The extracted markup is byte-for-byte identical:

```text
baseline length 16126 new length 16126
identical: true
```

This covers the header, hero, value rail, features, steps, role tabs, CTA, and
footer, including all classes, copy, ARIA attributes, and SVG markup.

## Risks

- `--font-mono` now resolves to the system monospace stack instead of Geist
  Mono. This is the intended change; the landing page does not use `font-mono`,
  so its visual output is unchanged. Other pages that use `font-mono` will see
  the system mono font.
- The header and role tabs are now separate client islands. Their state is
  independent, matching the original component (the original had two separate
  `useState` hooks with no cross-dependency).
- `menuItems` is passed from the server component to `LandingHeader` as a
  serializable prop; the rendered links are unchanged.
- `landing-arrow.tsx` is compiled into both the server and client graphs. It is
  a 5-line presentational component with no server-only imports.
- The worktree `node_modules` symlink still prevents a plain Turbopack build
  until a real install is present; this is a setup issue, not a code issue.

## Follow-ups

- If further landing JS reduction is needed, consider CSS-only mobile menu and
  role tabs (would change DOM/behavior and is out of scope here).
- Add component tests for the two client islands (mobile menu toggle, role tab
  switch) once the frontend test setup includes Next component mocks.
- Fix `scripts/worktree_setup.sh` to use a real `npm ci` or configure the
  Turbopack root so plain `npm run build` works in worktrees.
- Update `docs/cleanup/STATUS.md` initial-JS `/` metric with the numbers above
  during final integration.
