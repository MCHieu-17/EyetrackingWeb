#!/usr/bin/env bash
# Chuẩn bị worktree cho agent: symlink .venv và node_modules từ repo chính.
#
#   ./scripts/worktree_setup.sh ../EyeLearning-worktrees/<task-id>
set -euo pipefail

WORKTREE="${1:?usage: $0 <worktree-path>}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -d "$WORKTREE" ]; then
    echo "worktree không tồn tại: $WORKTREE" >&2
    exit 1
fi

if [ -d "$ROOT_DIR/backend/.venv" ]; then
    ln -sfn "$ROOT_DIR/backend/.venv" "$WORKTREE/backend/.venv"
fi

if [ -d "$ROOT_DIR/frontend/node_modules" ]; then
    ln -sfn "$ROOT_DIR/frontend/node_modules" "$WORKTREE/frontend/node_modules"
fi

echo "OK: $WORKTREE"
