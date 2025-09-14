#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"

# Prefer repo-level .venv python; fallback to system python3
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PY_EXE="$REPO_ROOT/.venv/bin/python"
else
  PY_EXE="python3"
fi

echo "[1/2] Running tests…"
if "$PY_EXE" -c 'import importlib.util as u, sys; sys.exit(0 if u.find_spec("pytest") else 1)'; then
  "$PY_EXE" -m pytest -q "$ROOT_DIR/tests" || true
else
  echo "pytest not installed; skipping tests."
fi

echo "[2/2] Starting server on :7060 (Ctrl+C to stop)"
exec "$PY_EXE" "$ROOT_DIR/server/app.py" --host 127.0.0.1 --port 7060

