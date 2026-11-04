#!/usr/bin/env bash
# Promotion is deliberately gated on recorded acceptance results.
set -euo pipefail
cd "$(dirname "$0")/.."
python - <<'PY'
import json
from pathlib import Path
path=Path('docs/test-evidence/graph-release-gate.json')
if not path.exists() or not json.loads(path.read_text()).get('performance_and_ai_gate_passed'):
    raise SystemExit('Refusing rollout: chatbot graph acceptance gate has not passed. See docs/chatbot-graph-implementation-status.md.')
PY
# Keep the previous image before Compose retags the newly built service.
docker image tag eyelearning-chatbot:local eyelearning-chatbot:before-graph
docker compose build chatbot backend frontend nginx
docker compose up -d chatbot backend frontend nginx
