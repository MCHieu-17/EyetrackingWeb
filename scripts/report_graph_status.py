"""Build a reviewable acceptance report from saved evidence, without network calls."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
evidence=root/'docs/test-evidence'
quality_path=evidence/'graph-live-final.json'
quality=json.loads(quality_path.read_text()) if quality_path.exists() else {}
if not quality.get('summary'):
    quality_path=evidence/'graph-live-regression.json'
    quality=json.loads(quality_path.read_text())
summary=quality.get('summary',{})
focused_path=evidence/'graph-retry-knowledge10.json'
focused=json.loads(focused_path.read_text()) if focused_path.exists() else {}
focused_stats=focused.get('summary',{}).get('knowledge',{})
focused_text=(f"Final focused Knowledge QA at 10 concurrent chats: {focused.get('quality_rate',0):.1%} automated quality, {focused_stats.get('completed')}/{focused_stats.get('count')} normal verified completions; P95 first content {focused_stats.get('p95_first_content',0):.3f} s. The profile is 1 River request/second, generation=4, verify=2, total=6 and one bounded generator/verifier HTTP retry. These conservative values are now the candidate defaults. See `graph-retry-knowledge10.json` and `graph-final-river-metrics.json`." if focused else "Final focused result pending.")

rows=[]
for name in ('graph-retry-knowledge10.json','graph-paced-knowledge10-smoke.json','graph-paced-knowledge10.json','graph-final-knowledge15.json','graph-final-knowledge10.json','graph-baseline-knowledge30.json','graph-final-knowledge30-ingest.json','graph-eval-general30.json','graph-eval-lms30.json','graph-eval-mixed30.json'):
    if not (evidence/name).exists(): continue
    data=json.loads((evidence/name).read_text())
    for route,stats in data['summary'].items():
        valid=sum(r.get('done',{}).get('verified') is True and r.get('done',{}).get('finish_reason','stop')=='stop' for r in data['runs'] if r['route']==route)
        rows.append(f"| {name} | {route} | {stats['completed']}/{stats['count']} | {valid} | {stats['p95_first_content']:.3f} s | {stats['p95_total']:.3f} s |")
report=f'''# Chatbot graph: implementation and acceptance evidence

The new source uses one parent LangGraph and three compiled subgraphs. Implementation
and deterministic verification are complete for the features below. **Live acceptance
has not passed; the serving containers and previous image were not replaced.** No
course, slide, embedding, history or assignment data was deleted or rebuilt in the
application database. Regression and AI fixtures use separate disposable databases.

## Implemented behavior

- Whole-utterance greetings/thanks/capabilities and simple LMS requests bypass AI.
  Mixed greetings use routing. One async routing call separates mixed requests,
  resolves follow-up searches and uses trusted current assignment metadata. Router
  failures ask for clarification; quota/timeouts explicitly report overload.
- Knowledge QA keeps 20 vector/FTS candidates, RRF and eight slides, scoped to the
  authorized course. Citation metadata is built by code. NDJSON blocks are buffered
  whole, checked cumulatively, and only approved blocks are streamed. The queue is
  bounded at two; one repair is allowed for the entire turn; accepted text is never
  rewritten. Unknown citation IDs, unmatched evidence and disclosure checks fail closed.
  Knowledge answers cannot supplement missing slide facts with outside knowledge.
- LMS exposes only fixed internal reads. Student/course come from the DB session;
  context versions, enrollment, course availability and teacher locks are rechecked.
  Draft quizzes, other courses and other students' results are excluded. Duplicate
  names require selection. Deadline arithmetic uses min(due_at, started_at+duration),
  server time and Asia/Ho_Chi_Minh display. Missing deadlines are explicit.
- Independent mixed lookup/retrieval runs concurrently, emits LMS first, then knowledge.
  Dependent knowledge waits for the resolved backend object.
- SSE keeps session/status/citations/token/done/error, adds route/block_id and final
  routes/finish_reason. Only filtered custom graph events reach the API. The backend
  checks access before forwarding blocks and saving, and periodically while waiting.
  Disconnects cancel speculative generation and async River calls; unfinished transport
  streams have no fabricated done or completed assistant history.
- UI renders each approved block immediately, including GFM tables, math and code,
  with the existing eye-tracking attributes. No artificial typing delay or raw HTML.
- Shared AsyncOpenAI connection pool, separate router/generator/verifier budgets,
  total concurrency and request pacing; bounded queues/timeouts and no infinite retry (router: zero retries; generator/verifier: at most one SDK transport retry before completion/stream creation).
  One GPU model worker serves both ingestion and chat, query-priority batches <=8,
  collection <=10 ms, query-only LRU of 1,024 entries/15 minutes. VLM ingestion has
  bounded concurrency and yields admission while chat is active. Existing selective
  ingestion and stored vectors are retained.
- Python 3.12 image, LangGraph 1.2.19, one app worker, GPU warm-up/readiness, internal
  backend URL, nginx buffering disabled, heartbeat/wait events, stage/usage/429 and
  rejected-block logs. The old whole-answer orchestration is removed from the path.

## Verification

- Backend: 30 regression tests passed (including real PostgreSQL/HTTP integration).
  The four internal LMS tests passed again after the connection/query optimization.
- Chatbot: 92 tests passed in the Python 3.12 container, including six PostgreSQL
  ingestion/retrieval tests. Unit coverage includes cancellation, cumulative approval,
  a single repair, citation rejection, route composition and priority admission.
- Frontend: TypeScript check passed; 10 Markdown/SSE unit tests and nine Playwright
  tests passed. The browser test explicitly holds done and observes the first block,
  rendered math, table and code, plus existing access-revocation/teacher-toggle tests.
- Real AI regression: {summary.get('passed')}/{summary.get('total')} cases passed all
  automated correctness/usefulness/context/citation criteria; quality rate
  {summary.get('quality_rate',0):.1%}; {summary.get('answer_leaks')} detected answer leaks;
  {summary.get('missing_judgments')} missing judgments. Source: `{quality_path.name}`.
  Automated judgments are supporting evidence and require review, especially quiz hints.

## Final reduced-load profile

{focused_text}

The full mixed/hint/review regression result above predates this conservative quota profile; its usefulness failures remain review/retest items. Focused knowledge quality does not replace that broader regression.

## Load measurements

NVIDIA GeForce RTX 3060, 12,478,906,368 bytes VRAM, CUDA 12.4, one application worker;
River model remains the configured DeepSeek-V4.1-Flash-1017. Provider quota is not
exposed. River returned HTTP 429 `account_rate` (account request rate exceeded for
this model). Measurements cover internal service SSE plus real backend callbacks; browser paint/public-proxy latency is not included. Latency includes actual first content, never status as a substitute.

| Evidence | Route | Completed | Verified normal finishes | P95 first content | P95 total |
|---|---|---:|---:|---:|---:|
{chr(10).join(rows)}

**First-content timings above include handled overload/fallback text. They are NOT
proof of the Knowledge QA verified-block target.** Completion counts also do not
mean correct/useful answers. Baseline has missing completions; the datasets use the
same fixed questions/hardware/model but separate synthetic fixture snapshots, so a
strict 40% success-latency comparison requires a clean comparable rerun. Mixed load
and all-knowledge load with concurrent real VLM ingest both ran; all-knowledge ingest
processed three pages with zero ingest failures. A GPU sample during the 15-concurrent test showed 4,440 / 12,288 MiB used and 43% utilization (whole GPU, including existing services). Peak VRAM during the 30-request burst
was not captured; the model and GPU warm-up were verified.

The user subsequently requested 15 and 10 concurrent chats. Those measurements are included above; neither completing an HTTP stream nor emitting an overload message is counted as successful Knowledge QA.

The 0.5 s greeting first-content and 2 s LMS targets passed in the saved runs.
The 10 s Knowledge QA target, full mixed/hint/review quality gate and original 30-concurrent acceptance
have **not** passed. The final 30-sample Knowledge QA run at 10 concurrent chats did pass the focused 90% quality and no-fallback checks. Zero detected leaks in this sample does not override those gates.
See `graph-release-gate.json`; rollout is blocked until all required checks pass.

## Reproduce and release

1. Create the dedicated PostgreSQL instance as documented by `test_graph_stack.sh`;
   run `bash scripts/test_graph_stack.sh` (regression DB is reset by fixtures).
2. Run `bash scripts/prepare_graph_eval.sh`; keep the eval DB separate from regression.
3. Start backend/chatbot candidates on distinct ports using the eval database, shared
   internal token and existing read-only weights volume. Run `benchmark_graph.py`
   with `--concurrency 30` for mixed/knowledge, plus `--ingest`, and `evaluate_live.py`
   for the 30-case real-provider regression. Configure River limits from actual quota.
4. `bash scripts/build_graph_test.sh` verifies the production-derived Python 3.12 image.
   `scripts/graph_release_gate.py` evaluates saved performance/AI acceptance. The
   promotion script refuses rollout unless its recorded gate passes. Review security
   evidence and rerun matching source/image/fixtures before promotion.

Rollback image retained: `sha256:61a26f811eab5da6f898247df6dfd6b5477a81af8bfff60c458f085a4f25da11`.
The serving `eyetracking-chatbot` image was not retagged or restarted. The promotion
script also tags `eyelearning-chatbot:before-graph` before a successful promotion.
'''
(root/'docs/chatbot-graph-implementation-status.md').write_text(report)
print('Wrote docs/chatbot-graph-implementation-status.md')
