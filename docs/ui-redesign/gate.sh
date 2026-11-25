#!/usr/bin/env bash
# Gate tự động sau mỗi task opencode. Exit != 0 nếu vi phạm luật cứng.
#   docs/ui-redesign/gate.sh "<regex phạm vi file được sửa>"
# Ví dụ: docs/ui-redesign/gate.sh '^frontend/components/ui/'
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
SCOPE="${1:?usage: gate.sh <scope-regex>}"
fail=0

changed="$(git status --porcelain | awk '{print $NF}' | grep -v '^docs/ui-redesign/logs/' || true)"
echo "== File thay đổi"; echo "$changed" | sed 's/^/  /'

out_of_scope="$(echo "$changed" | grep -vE "$SCOPE" | grep -vE '^frontend/components/ui/icon\.tsx$' | grep -v '^$' || true)"
if [ -n "$out_of_scope" ]; then
  echo "!! Ngoài phạm vi:"; echo "$out_of_scope" | sed 's/^/  /'; fail=1
fi

if git status --porcelain -- backend services db scripts frontend/package.json frontend/package-lock.json frontend/e2e | grep -q .; then
  echo "!! Đụng vùng cấm (backend/services/db/scripts/package/e2e)"; fail=1
fi

grep -rnoE 'data-aoi(-[a-z]+)?=("[^"]*"|\{[^}]*\})' frontend/components frontend/app | sort > /tmp/aoi-after.txt
if [ -f /tmp/aoi-before.txt ] && ! diff -q <(cut -d: -f1,3- /tmp/aoi-before.txt) <(cut -d: -f1,3- /tmp/aoi-after.txt) >/dev/null; then
  echo "!! Thuộc tính data-aoi thay đổi:"; diff <(cut -d: -f1,3- /tmp/aoi-before.txt) <(cut -d: -f1,3- /tmp/aoi-after.txt) | head -20; fail=1
fi

# Vùng AOI: chỉ cho phép đổi class màu. Báo các dòng diff có token layout.
AOI_FILES='frontend/components/(reader|student/learning-reader|quiz/inline-quiz|assistant|calibration)/|frontend/components/quiz/lazy-inline-quiz|frontend/components/teacher/aoi/student-preview|frontend/components/teacher/visualization/replay/replay-stage'
aoi_changed="$(echo "$changed" | grep -E "$AOI_FILES" || true)"
if [ -n "$aoi_changed" ]; then
  layout_re='\b(-?m[trblxy]?|p[trblxy]?|gap(-[xy])?|space-[xy]|w|h|min-[wh]|max-[wh]|size|text-(xs|sm|base|lg|[0-9]xl)|leading|font-(medium|semibold|bold|normal)|rounded(-[a-z0-9]+)?|border(-[trblxy])?(-[0-9])?|flex|grid|inline|block|hidden|absolute|relative|fixed|sticky|inset|top|left|right|bottom|translate|scale)-?\[?[0-9a-z./%-]*\]?'
  for f in $aoi_changed; do
    removed="$(git diff -U0 -- "$f" | grep '^-[^-]' | grep -oE "$layout_re" | sort)"
    added="$(git diff -U0 -- "$f" | grep '^+[^+]' | grep -oE "$layout_re" | sort)"
    if [ "$removed" != "$added" ]; then
      echo "!! $f: class layout thay đổi trong vùng AOI (chỉ được đổi màu)"
      diff <(echo "$removed") <(echo "$added") | head -10 | sed 's/^/    /'
      fail=1
    fi
  done
fi

hex="$(echo "$changed" | grep -E '\.(tsx|css)$' | grep -vE 'brand-logo|microsoft-logo|lib/aoi/colors' | xargs -r grep -nE '\[#[0-9a-fA-F]{3,8}\]' 2>/dev/null || true)"
if [ -n "$hex" ]; then
  echo "-- Còn hex trong className (cảnh báo):"; echo "$hex" | head -15 | sed 's/^/  /'
fi

# Thuộc tính hành vi (handler, aria, role, asChild…) không được mất.
attrs_re='\b(on[A-Z][a-zA-Z]+|href|disabled|aria-[a-z]+|role|id|htmlFor|type|asChild|name|value|checked|tabIndex)='
rm_attrs="$(git diff -U0 -- frontend | grep -E '^-[^-]' | grep -oE "$attrs_re" | sort)"
add_attrs="$(git diff -U0 -- frontend | grep -E '^\+[^+]' | grep -oE "$attrs_re" | sort)"
missing="$(comm -23 <(echo "$rm_attrs" | uniq -c | awk '{print $2" "$1}' | sort) <(echo "$add_attrs" | uniq -c | awk '{print $2" "$1}' | sort) || true)"
if [ -n "$(echo "$missing" | tr -d '[:space:]')" ]; then
  echo "!! Thuộc tính hành vi bị xoá/giảm (kiểm tra tay):"; echo "$missing" | sed 's/^/    /'; fail=1
fi
# asChild dạng boolean (không có '=')
rm_as=$(git diff -U0 -- frontend | grep -E '^-[^-]' | grep -oE '\basChild\b' | wc -l)
add_as=$(git diff -U0 -- frontend | grep -E '^\+[^+]' | grep -oE '\basChild\b' | wc -l)
if [ "$rm_as" -gt "$add_as" ]; then echo "!! asChild bị mất ($rm_as → $add_as)"; fail=1; fi

echo "== lint + typecheck"
(cd frontend && npm run -s lint && npm run -s typecheck) || fail=1

[ "$fail" -eq 0 ] && echo "== GATE PASS" || echo "== GATE FAIL"
exit "$fail"
