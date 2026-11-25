#!/usr/bin/env bash
# Giao một task UI cho opencode, tự chuyển provider khi hết quota/rate limit.
#
#   docs/ui-redesign/run-task.sh 01-ui-primitives            # task mới
#   docs/ui-redesign/run-task.sh 01-ui-primitives "sửa: ..."  # tiếp session cũ với feedback
#
# Thứ tự model: river-02 → river-03 → tokenharbor → tokenharbor-fast.
# Log: docs/ui-redesign/logs/<task>.<n>.jsonl ; session id: logs/<task>.session
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASK="${1:?usage: run-task.sh <task-name> [feedback]}"
FEEDBACK="${2:-}"
LOGDIR="$ROOT/docs/ui-redesign/logs"
mkdir -p "$LOGDIR"
SESSION_FILE="$LOGDIR/$TASK.session"
MODEL_FILE="$LOGDIR/.model-index"

MODELS=(
  "river-02/deepseek-v4.1-flash-1017"
  "river-03/deepseek-v4.1-flash-1017"
  "tokenharbor/deepseek-v4.1-flash-1017"
  "tokenharbor/deepseek-v4.1-flash-1017-fast"
)
# Bắt đầu từ model còn quota gần nhất (provider đã cạn thì không thử lại).
idx="$(cat "$MODEL_FILE" 2>/dev/null || echo 0)"

if [ -n "$FEEDBACK" ]; then
  PROMPT="Review của điều phối viên cho task docs/ui-redesign/tasks/$TASK.md — hãy sửa đúng các điểm sau, không làm gì ngoài phạm vi, rồi chạy lại lint + typecheck:
$FEEDBACK"
else
  PROMPT="Bạn là frontend engineer. Đọc AGENTS.md (mục 0, 3, 12), docs/ui-redesign/PLAN.md, rồi thực hiện ĐÚNG docs/ui-redesign/tasks/$TASK.md.
- Chỉ sửa file trong phạm vi task. Không sửa backend/, services/, db/, scripts/, benchmarks/, frontend/e2e/, package.json.
- Không cài package, không commit, không chạy git checkout/reset/stash.
- Giữ nguyên chữ hiển thị, aria-label, role, id mà task liệt kê.
- Làm hết mọi file trong phạm vi, không bỏ dở. Xong chạy: cd frontend && npm run lint && npm run typecheck, sửa đến khi sạch.
- Cuối cùng in tóm tắt: danh sách file đã sửa + điểm nào chưa làm được."
fi

is_quota_error() {
  grep -qiE '429|rate.?limit|quota|insufficient|exceeded|billing|credit|too many requests|unauthori[sz]ed|401|403 forbidden|overloaded|503' "$1"
}

attempt=0
while [ "$idx" -lt "${#MODELS[@]}" ]; do
  model="${MODELS[$idx]}"
  attempt=$((attempt + 1))
  log="$LOGDIR/$TASK.$(date +%H%M%S).$attempt.jsonl"
  args=(run -m "$model" --auto --format json --title "ui-$TASK")
  if [ -s "$SESSION_FILE" ]; then
    args+=(-s "$(cat "$SESSION_FILE")")
  fi
  echo "[run-task] $TASK → $model (log: ${log#$ROOT/})" >&2
  (cd "$ROOT" && timeout 2400 opencode "${args[@]}" "$PROMPT") >"$log" 2>&1
  code=$?

  sid="$(grep -oE '"sessionID":"[^"]+"' "$log" | head -1 | cut -d'"' -f4)"
  [ -n "$sid" ] && echo "$sid" >"$SESSION_FILE"

  # Thành công: exit 0 và không có lỗi quota trong phần cuối log.
  if [ "$code" -eq 0 ] && ! tail -c 4000 "$log" | grep -qiE '"type":"error"'; then
    echo "[run-task] xong với $model (session ${sid:-?})" >&2
    echo "$idx" >"$MODEL_FILE"
    exit 0
  fi
  if tail -c 8000 "$log" | is_quota_error /dev/stdin; then
    echo "[run-task] $model hết quota/rate limit → chuyển model kế tiếp" >&2
    idx=$((idx + 1))
    echo "$idx" >"$MODEL_FILE"
    continue
  fi
  echo "[run-task] $model lỗi (exit $code), không phải quota — xem log" >&2
  exit "$code"
done
echo "[run-task] hết model khả dụng" >&2
exit 3
