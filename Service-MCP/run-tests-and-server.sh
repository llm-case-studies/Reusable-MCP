#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"

if [ -x "$REPO_ROOT/.venv/bin/python" ]; then PY_EXE="$REPO_ROOT/.venv/bin/python"; else PY_EXE="python3"; fi

echo "[1/2] Running tests…"
if "$PY_EXE" -c 'import importlib, sys; sys.exit(0 if importlib.util.find_spec("pytest") else 1)'; then
  "$PY_EXE" -m pytest -q "$ROOT_DIR/tests" || true
else
  echo "pytest not installed; skipping tests."
fi

echo "[2/2] Starting server on :7030 (Ctrl+C to stop)"
echo "Service-MCP: scaffold only. Server not implemented yet."
exit 0

