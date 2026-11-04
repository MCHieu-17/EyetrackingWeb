#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker build -t eyelearning-chatbot:graph-candidate services/chatbot
docker build -t eyelearning-chatbot:graph-test -f services/chatbot/Dockerfile.test services/chatbot
docker run --rm --network host -e CHATBOT_INTEGRATION_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:55439/eyelearning_test -v "$PWD/services/chatbot/tests:/tests:ro" eyelearning-chatbot:graph-test
