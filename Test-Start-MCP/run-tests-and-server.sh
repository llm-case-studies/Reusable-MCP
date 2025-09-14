#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"

# Prefer repo-level .venv, then service .mcp-venv, then system python3
REPO_VENV_PY="$REPO_ROOT/.venv/bin/python"
SVC_VENV_PY="$ROOT_DIR/.mcp-venv/bin/python"
if [ -x "$REPO_VENV_PY" ]; then
  PY_EXE="$REPO_VENV_PY"
elif [ -x "$SVC_VENV_PY" ]; then
  PY_EXE="$SVC_VENV_PY"
else
  PY_EXE="python3"
fi

echo "== Test-Start-MCP (scaffold) =="
echo "  PY_EXE=$PY_EXE ($(command -v "$PY_EXE" || echo not-found))"
echo "  repo venv: $REPO_ROOT/.venv (preferred)"

if ! "$PY_EXE" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
  echo "Missing deps: fastapi, uvicorn."
  echo "Create/activate repo venv and install:"
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -U pip fastapi uvicorn pytest" >&2
fi

echo "[1/2] Running tests…"
if "$PY_EXE" - <<'PY' 2>/dev/null; then :; else echo "pytest not found; skipping tests."; fi
import importlib, sys
sys.exit(0 if importlib.util.find_spec('pytest') else 1)
PY
then
  "$PY_EXE" -m pytest -q "$ROOT_DIR/tests" || true
fi

echo "[2/2] Starting server on :7060 (Ctrl+C to stop)"
echo "Test-Start-MCP: scaffold only. Server not implemented yet."
echo "See docs/SPEC.md and docs/QUICKSTART.md for the intended behavior and APIs."
exit 0
