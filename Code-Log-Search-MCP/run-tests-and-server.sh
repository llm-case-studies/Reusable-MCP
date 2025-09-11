#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "== Running tests =="
if command -v pytest >/dev/null 2>&1; then
  pytest -q "$ROOT_DIR/tests" || { echo "Tests failed" >&2; exit 1; }
else
  echo "pytest not found; skipping tests. Run: pip install pytest"
fi

echo "\n== Starting server (Ctrl+C to stop) =="
exec python3 "$ROOT_DIR/server/app.py" --default-code-root "${CLS_CODE_ROOT:-$ROOT_DIR}" --logs-root "${RN_LOG_DIR:-$HOME/.roadnerd/logs}" "$@"

