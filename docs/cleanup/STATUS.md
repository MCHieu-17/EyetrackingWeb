# Cleanup status

## Baseline

- Branch: `cleanup/base`
- Commit: (điền sau khi commit)
- Date: 2026-11-09

### Static checks

| Check | Result |
|---|---|
| ruff | pending |
| eslint | pending |
| tsc | pending |
| knip | pending |
| pytest | pending |
| frontend build | pending |
| smoke | pending |

### Metrics

| Metric | Baseline | Target | After |
|---|---|---|---|
| Gaze batch queries | pending | ≤ 5 | |
| Teacher course list queries | pending | ≤ 10 | |
| Course students queries | pending | ≤ 10 | |
| Media asset queries | pending | ≤ 5 | |
| Initial JS `/` | pending | ≤ baseline | |
| Initial JS `/student` | pending | ≤ baseline | |
| Initial JS `/teacher` | pending | ≤ baseline | |

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
