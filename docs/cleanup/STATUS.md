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
| pytest | 28 passed |
| frontend build | pass |
| smoke | pass |

### Metrics

| Metric | Baseline | Target | After |
|---|---|---|---|
| Gaze batch queries | pending (P4 harness) | ≤ 5 | |
| Teacher course list queries | pending (P4 harness) | ≤ 10 | |
| Course students queries | pending (P4 harness) | ≤ 10 | |
| Media asset queries | pending (P4 harness) | ≤ 5 | |
| Client JS chunks total | 2,516.0 KB (57 chunks) | ≤ baseline | |
| Initial JS `/` | pending (route manifest) | ≤ baseline, tốt nhất −10% | |
| Initial JS `/student` | pending (route manifest) | ≤ baseline | |
| Initial JS `/teacher` | pending (route manifest) | ≤ baseline | |

## Waves

| Wave | Status | Tag | Notes |
|---|---|---|---|
| 0 | in progress | | Foundation |
| 1 | pending | | Quick wins + test infra |
| 2 | pending | | Backend split |
| 3 | pending | | ORM performance |
| 4 | pending | | Frontend split |
| 5 | pending | | Scale readiness |
| 6 | pending | | Final integration |
