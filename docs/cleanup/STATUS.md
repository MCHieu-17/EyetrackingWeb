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
| frontend unit tests | 222 passed (wave 4) |
| frontend build | pass |
| smoke | pass |
| migrations | pass |

### Metrics

| Metric | Baseline | Target | After |
|---|---|---|---|
| Gaze batch queries | 14 (P4 baseline) | ≤ 5 | 9 (P1) |
| Teacher course list queries | 6 (P4 baseline) | ≤ 10 | 6 |
| Course students queries | 9 (P4 baseline) | ≤ 10 | 9 |
| Media asset queries | 17 (P4 baseline) | ≤ 5 | 4 (P2) |
| Client JS chunks total | 2,516.0 KB (57 chunks, webpack analyze) | ≤ baseline | 2,334.8 KB (44 chunks, Turbopack build — not directly comparable) |
| Initial JS `/` | pending (route manifest) | ≤ baseline, tốt nhất −10% | |
| Initial JS `/student` | pending (route manifest) | ≤ baseline | |
| Initial JS `/teacher` | pending (route manifest) | ≤ baseline | |

## Waves

| Wave | Status | Tag | Notes |
|---|---|---|---|
| 0 | done | | Foundation |
| 1 | done | `cleanup/wave-1` | Quick wins + test infra (A1–A4 merged) |
| 2 | done (backend) | | Backend split B1–B4 merged |
| 3 | done (backend) | | ORM performance P1–P4 merged |
| 4 | done | | Frontend split F1–F5 merged |
| 5 | pending | | Scale readiness |
| 6 | pending | | Final integration |
