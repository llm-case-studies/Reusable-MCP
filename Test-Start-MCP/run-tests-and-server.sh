#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"

# Network (edit if needed)
HOST="${TSM_HOST:-127.0.0.1}"
PORT="${TSM_PORT:-7060}"

# ----- Configurable policy/env (edit as needed) -----
# Default to allowing scripts only within this service folder.
export TSM_ALLOWED_ROOT="${TSM_ALLOWED_ROOT:-$ROOT_DIR}"
# Allow this service's runner by default; add more paths separated by ':'
# Include local runner and probe script by default (colon-separated)
export TSM_ALLOWED_SCRIPTS="${TSM_ALLOWED_SCRIPTS:-$ROOT_DIR/run-tests-and-server.sh:$ROOT_DIR/scripts/probe.py}"
# Allowed flags for run scripts (comma-separated)
export TSM_ALLOWED_ARGS="${TSM_ALLOWED_ARGS:---no-tests,--kill-port,--smoke,--host,--port,--default-code-root,--logs-root,--home,--repeat,--sleep-ms,--exit-code,--stderr-lines,--bytes,--json,--ping}"
# Env vars that may be passed through to child processes
export TSM_ENV_ALLOWLIST="${TSM_ENV_ALLOWLIST:-CLS_TOKEN,PRIOR_TOKEN,MEM_TOKEN}"
# Logging
export TSM_LOG_DIR="${TSM_LOG_DIR:-$ROOT_DIR/logs}"
export TSM_LOG_LEVEL="${TSM_LOG_LEVEL:-INFO}"

# Prefer repo-level .venv python; fallback to system python3
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PY_EXE="$REPO_ROOT/.venv/bin/python"
else
  PY_EXE="python3"
fi

# Free the port if occupied (singleton server)
echo "[prep] Ensuring nothing listens on $HOST:$PORT …"
if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -ti TCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$PIDS" ]; then
    echo "[prep] Killing PIDs on :$PORT: $PIDS"
    kill $PIDS 2>/dev/null || true; sleep 0.3; kill -9 $PIDS 2>/dev/null || true
  fi
fi
if command -v fuser >/dev/null 2>&1; then
  fuser -k -TERM "${PORT}/tcp" 2>/dev/null || true; sleep 0.3; fuser -k -KILL "${PORT}/tcp" 2>/dev/null || true
fi

echo "[1/2] Running tests…"
if "$PY_EXE" -c 'import importlib.util as u, sys; sys.exit(0 if u.find_spec("pytest") else 1)'; then
  "$PY_EXE" -m pytest -q "$ROOT_DIR/tests" || true
else
  echo "pytest not installed; skipping tests."
fi

# Ensure probe script is executable
if [ -f "$ROOT_DIR/scripts/probe.py" ]; then
  chmod +x "$ROOT_DIR/scripts/probe.py" || true
fi

echo "[2/2] Starting server on $HOST:$PORT (Ctrl+C to stop)"
exec "$PY_EXE" "$ROOT_DIR/server/app.py" --host "$HOST" --port "$PORT"
