#!/usr/bin/env bash
# Chạy smoke thật trước merge: gaze model + chatbot RAG + E2E.
# Cần stack, GPU/weights và LLM/VLM thật.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

printf '\n=== gaze smoke ===\n'
DEVICE="${DEVICE:-cpu}" ./scripts/test_gaze.sh smoke

printf '\n=== chatbot RAG smoke ===\n'
./scripts/test_chatbot.sh smoke

printf '\n=== frontend E2E ===\n'
./scripts/e2e.sh

printf '\n[tests] smoke OK\n'
