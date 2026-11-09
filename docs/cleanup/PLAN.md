# Cleanup plan — agent-first

Mục tiêu: làm sạch codebase theo từng wave nhỏ, không đổi hành vi người dùng/API,
có test và metric trước/sau. Mỗi task do một agent sở hữu một worktree riêng.

## Nguyên tắc

- Không big-bang; mỗi task là một branch/worktree độc lập.
- Không đổi API path/response, auth/CSRF, gaze protocol.
- Không đổi schema DB trừ migration `002_...` ở Phase 5.
- Không sửa `db/migrations/001_baseline.sql`.
- Mỗi task ≤ 15 file / ≤ 800 LOC thay đổi.
- Mọi function public mới/đổi phải có test.
- Merge theo thứ tự; chạy gate sau mỗi merge.

## Worktree / branch

```text
cleanup/base
└── cleanup/integration
    ├── cleanup/p1-a1-backend-config
    ├── cleanup/p1-a2-frontend-api
    ├── cleanup/p1-a3-chatbot-dedup
    ├── cleanup/p1-a4-test-infra
    ├── cleanup/p2-b1-content-split
    ├── ...
```

Tạo worktree:

```bash
git worktree add ../EyeLearning-worktrees/<task-id> -b cleanup/<task-id> cleanup/integration
./scripts/worktree_setup.sh ../EyeLearning-worktrees/<task-id>
```

## File ownership

Một file chỉ có một owner tại một thời điểm. Nếu cần sửa file ngoài ownership,
dừng và báo coordinator.

| File/dir | Owner |
|---|---|
| `backend/app/models/**` | Frozen (trừ S1 Phase 5) |
| `backend/app/main.py` | S1 Phase 5 |
| `backend/app/api/access.py` | B4 Phase 2 → P2 Phase 3 |
| `backend/app/services/content/**` | B1 Phase 2 |
| `backend/app/services/analysis/**` | B2 Phase 2 → P3 Phase 3 |
| `backend/app/services/aoi/**` | B3 Phase 2 → P2 Phase 3 |
| `backend/app/services/metrics.py` | B3 Phase 2 → P3 Phase 3 |
| `backend/app/api/routes/gaze_ingest.py` | P1 Phase 3 |
| `backend/app/api/routes/learning_sessions.py` | P1 Phase 3 |
| `backend/app/api/routes/media.py` | P2 Phase 3 |
| `backend/app/api/routes/quiz_specs.py` | P2 Phase 3 |
| `backend/app/api/routes/chat.py` | P3 Phase 3 |
| `backend/app/api/routes/courses.py` | S1 Phase 5 |
| `backend/app/api/routes/lessons.py` | S1 Phase 5 |
| `backend/app/worker.py` | B4 Phase 2 → S1 Phase 5 |
| `backend/app/content_worker.py` | B4 Phase 2 |
| `db/migrations/**` | S1 Phase 5 |
| `docker-compose.yml` | S1 Phase 5 |
| `frontend/lib/api/client.ts` | A2 Phase 1 |
| `frontend/lib/api/chat.ts` | A2 Phase 1 |
| `frontend/lib/api/teacher.ts` | A2 Phase 1 |
| `frontend/lib/utils.ts` | A2 Phase 1 |
| `frontend/lib/query-keys.ts` | A2 Phase 1 |
| `frontend/lib/api/calibration.ts` | A2 Phase 1 |
| `frontend/lib/types/domain.ts` | Frozen |
| `frontend/components/ui/**` | Frozen |
| `frontend/components/teacher/aoi/**` | F1 Phase 4 |
| `frontend/components/assistant/**` | F2 Phase 4 |
| `frontend/components/student/**`, `reader/**`, `quiz/**` | F3 Phase 4 |
| `frontend/components/teacher/content-editor/**`, `students-tab.tsx`, `course-workspace.tsx` | F4 Phase 4 |
| `frontend/components/landing/**`, `app/page.tsx`, `app/layout.tsx` | F5 Phase 4 |
| `frontend/package.json`, `package-lock.json` | A4 Phase 1 |
| `scripts/check.sh` | A4 Phase 1 |
| `README.md`, `docs/**` | S3 Phase 5 / final |

## Contracts

- `app.services.content`, `app.services.analysis`, `app.services.aoi` giữ public
  API qua `__init__.py` re-export.
- `app.services.metrics.course_students` vẫn tồn tại (wrapper).
- `lib/api/client.ts` giữ nguyên export hiện tại.
- `lib/query-keys.ts` là nguồn duy nhất cho query key.
- `lib/types/domain.ts` không đổi.
- `components/ui/**` không đổi props.
- `ReaderFrame` props không đổi.
- `LazyAoiEditor` export/props không đổi.

## Phases

### Phase 0 — Foundation (serial)

- Commit checkpoint, tạo `cleanup/base`, `cleanup/integration`.
- Tạo docs/scripts worktree.
- Chạy baseline: `check.sh --build`, `test_backend.sh`, `smoke.sh`,
  `npm run analyze`, `EXPLAIN ANALYZE` các query chính.
- Ghi baseline vào `STATUS.md`.

### Phase 1 — Quick wins + test infra (4 agent song song)

| Task | Nội dung |
|---|---|
| A1 | Backend config/dead code: DB pool env, worker poll setting, escape LIKE, xóa dead code |
| A2 | Frontend API/client dedup: CSRF/refresh, parse error, format date, query keys, calibration split |
| A3 | Chatbot dedup: `_history_messages`; bỏ ignore `mdast` |
| A4 | Test infra: `check.sh --full`, Vitest, Playwright smoke, Makefile |

Merge: A4 → A1 → A2 → A3.

### Phase 2 — Backend module split (4 agent song song)

| Task | Nội dung |
|---|---|
| B1 | `services/content.py` → `services/content/**` |
| B2 | `services/analysis.py` → `services/analysis/**` |
| B3 | `services/aoi.py` → `services/aoi/**`; `services/course_students.py` |
| B4 | `api/access.py` lesson dependency; `worker_loop.py` |

Merge: B3 → B1 → B2 → B4.

### Phase 3 — ORM performance (4 agent song song)

| Task | Nội dung |
|---|---|
| P1 | Gaze/learning hot path: bỏ load presentations/course graph |
| P2 | Media/quiz/AOI access: bỏ `db.get(Course)` nặng |
| P3 | Chat/analysis/metrics: bỏ selectin thừa |
| P4 | Query-count harness + benchmark |

Merge: P4 → P1 → P2 → P3.

### Phase 4 — Frontend component split (5 agent song song)

| Task | Nội dung |
|---|---|
| F1 | AOI components |
| F2 | Assistant components |
| F3 | Student reader/quiz/preflight |
| F4 | Teacher content editor/students |
| F5 | Landing/layout + font |

Merge: F5 → F1 → F2 → F3 → F4.

### Phase 5 — Scale readiness (3 agent song song)

| Task | Nội dung |
|---|---|
| S1 | Embedding job queue DB-backed + worker + migration |
| S2 | Maintenance worker |
| S3 | Observability/docs/backup |

Merge: S1 → S2 → S3.

### Phase 6 — Final integration

- Merge all, chạy full gate, so sánh metric, cập nhật docs, tag `cleanup/done`.

## Test gate

```bash
ruff check backend services/gaze services/chatbot
cd backend && .venv/bin/pytest -q
cd .. && ./scripts/test_migrations.sh
./scripts/smoke.sh

cd frontend
npm run lint
npm run typecheck
npm run knip
npm run test
npm run build
npm run analyze
npx playwright test
```

## Performance budgets

| Metric | Target |
|---|---|
| Gaze batch queries | ≤ 5 |
| Teacher course list queries | ≤ 10 |
| Course students queries | ≤ 10 |
| Media asset queries | ≤ 5 |
| Initial JS `/` | ≤ baseline, tốt nhất −10% |
| Initial JS `/student`, `/teacher` | ≤ baseline |
| p95 key endpoints | ≤ baseline |

## Task card template

Mỗi subagent nhận task card đầy đủ: Context, Goal, Owns, Forbidden, Contracts,
Steps, Deliverables, Acceptance, Test commands, Report format. Không dựa vào
conversation history.

Report: `docs/cleanup/reports/<task-id>.md` (mỗi agent chỉ ghi file của mình).
