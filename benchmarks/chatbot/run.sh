#!/usr/bin/env bash
# Chạy benchmark chatbot: query SSE, component, ingest.
#   benchmarks/chatbot/run.sh <run-dir> <fixtures> <tokens> [quick]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/benchmarks/lib/common.sh"

RUN_DIR="${1:?usage: run.sh <run-dir> <fixtures> <tokens> [quick]}"
FIXTURES="${2:?}"
TOKENS="${3:?}"
QUICK="${4:-}"
OUT="$RUN_DIR/chatbot"
mkdir -p "$OUT"

core_course_id="$(json_get "$FIXTURES" 'd["ids"]["core_course_id"]')"
ingest_lesson_id="$(json_get "$FIXTURES" 'd["ids"]["ingest_lesson_id"]')"
concurrency="1,5,10,20"
repeats=3
ingest_limit="${BENCH_INGEST_LIMIT:-4}"
question_limit=0
if [ "$QUICK" = "quick" ]; then
  concurrency="1,5"
  repeats=1
  ingest_limit="${BENCH_INGEST_LIMIT:-2}"
  question_limit=8
fi

log "Chatbot query trực tiếp"
compose exec -T --user root chatbot python /bench/chatbot/query_probe.py \
  --url http://127.0.0.1:8000 --mode chatbot \
  --fixtures "$(bench_path "$FIXTURES")" \
  --questions /bench/fixtures/chat_questions.template.jsonl \
  --concurrency "$concurrency" --repeats "$repeats" --limit "$question_limit" \
  --out "$(bench_path "$OUT/query-chatbot.json")"

log "Chatbot query qua backend"
compose exec -T --user root chatbot python /bench/chatbot/query_probe.py \
  --url http://backend:8001 --mode backend \
  --token-file "$(bench_path "$TOKENS")" \
  --fixtures "$(bench_path "$FIXTURES")" \
  --questions /bench/fixtures/chat_questions.template.jsonl \
  --concurrency "$concurrency" --repeats "$repeats" --limit "$question_limit" \
  --out "$(bench_path "$OUT/query-backend.json")"

log "Chatbot components: retriever"
compose exec -T --user root chatbot python /bench/chatbot/component_bench.py \
  --mode retriever --course-id "$core_course_id" \
  --iterations "$([ "$QUICK" = quick ] && echo 5 || echo 20)" \
  --out "$(bench_path "$OUT/components.json")"

log "Chatbot components: llm + embedding"
compose exec -T --user root chatbot python /bench/chatbot/component_bench.py \
  --mode all --course-id "$core_course_id" \
  --iterations "$([ "$QUICK" = quick ] && echo 3 || echo 10)" \
  --concurrency 4 \
  --out "$(bench_path "$OUT/components-all.json")"

log "Chatbot retrieval recall (ANN vs exact)"
compose exec -T --user root chatbot python /bench/chatbot/retrieval_probe.py \
  --course-id "$core_course_id" \
  --questions /bench/fixtures/chat_questions.template.jsonl \
  --limit 8 \
  --out "$(bench_path "$OUT/retrieval.json")"

log "Chatbot ingest (limit=$ingest_limit)"
compose exec -T --user root chatbot python /bench/chatbot/ingest_probe.py \
  --lesson-id "$ingest_lesson_id" --limit "$ingest_limit" \
  --out "$(bench_path "$OUT/ingest.json")"

echo "$OUT"
