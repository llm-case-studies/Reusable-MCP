#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "== Memory-MCP: running tests =="
if command -v pytest >/dev/null 2>&1; then
  pytest -q "$ROOT_DIR/tests" || { echo "Tests failed" >&2; exit 1; }
else
  echo "pytest not found; skipping tests. Run: pip install pytest"
fi

echo "\n== Starting Memory-MCP server (Ctrl+C to stop) =="
exec python3 "$ROOT_DIR/server/app.py" --home "${MEM_HOME:-$HOME/.roadnerd/memorydb}" "$@"

