# Cleanup status

## Baseline

- Branch: `cleanup/base`
- Commit: `7e4c77a`
- Date: 2026-11-09

### Static checks

| Check | Result |
|---|---|
| ruff | pass |
| eslint | pass |
| tsc | pass |
| knip | pass |
| pytest | 34 passed (wave 1) |
| frontend unit tests | 73 passed (wave 1) |
| frontend build | pass |
| smoke | pass |
| migrations | pass |

### Metrics

| Metric | Baseline | Target | After |
|---|---|---|---|
| Gaze batch queries | pending (P4 harness) | ≤ 5 | |
| Teacher course list queries | pending (P4 harness) | ≤ 10 | |
| Course students queries | pending (P4 harness) | ≤ 10 | |
| Media asset queries | pending (P4 harness) | ≤ 5 | |
| Client JS chunks total | 2,516.0 KB (57 chunks, webpack analyze) | ≤ baseline | 2,334.8 KB (44 chunks, Turbopack build — not directly comparable) |
| Initial JS `/` | pending (route manifest) | ≤ baseline, tốt nhất −10% | |
| Initial JS `/student` | pending (route manifest) | ≤ baseline | |
| Initial JS `/teacher` | pending (route manifest) | ≤ baseline | |

## Waves

| Wave | Status | Tag | Notes |
|---|---|---|---|
| 0 | done | | Foundation |
| 1 | done | `cleanup/wave-1` | Quick wins + test infra (A1–A4 merged) |
| 2 | in progress | | Backend split |
| 3 | pending | | ORM performance |
| 4 | in progress | | Frontend split |
| 5 | pending | | Scale readiness |
| 6 | pending | | Final integration |
