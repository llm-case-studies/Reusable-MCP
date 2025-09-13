#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$ROOT_DIR/.mcp-venv/bin/python"
if [ -x "$VENV_PY" ]; then
  PY_EXE="$VENV_PY"
else
  PY_EXE="python3"
fi
APP="$PY_EXE -m server.app"
HOME_DIR_DEFAULT="$HOME/.roadnerd/memorydb"
MEM_HOME="${MEM_HOME:-$HOME_DIR_DEFAULT}"
LOG_DIR="$ROOT_DIR/logs"
LOG_DIR="$ROOT_DIR/logs"

NO_TESTS=0
CLEAN_HOME=0
KILL_PORT=0
SMOKE=0

# Extract --host/--port from args to target health checks
HOST="127.0.0.1"
PORT="7090"
ARGS=( )
while (("$#")); do
  case "$1" in
    --no-tests) NO_TESTS=1; shift ;;
    --clean-home) CLEAN_HOME=1; shift ;;
    --kill-port) KILL_PORT=1; shift ;;
    --smoke) SMOKE=1; shift ;;
    --host) HOST="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --port) PORT="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --host=*|--port=*)
      # split on '='
      KEY="${1%%=*}"; VAL="${1#*=}"; [ "$KEY" = "--host" ] && HOST="$VAL" || PORT="$VAL"; ARGS+=("$1"); shift ;;
    *) ARGS+=("$1"); shift ;;
  esac
done

BASE_URL="http://$HOST:$PORT"
mkdir -p "$LOG_DIR"

echo "== Memory-MCP: settings =="
echo "  PY_EXE=$PY_EXE ($(command -v "$PY_EXE" || echo not-found))"
echo "  MEM_HOME=$MEM_HOME"
echo "  HOST=$HOST PORT=$PORT"
echo "  flags: no-tests=$NO_TESTS clean-home=$CLEAN_HOME kill-port=$KILL_PORT smoke=$SMOKE"

if (( CLEAN_HOME )); then
  echo "== Cleaning home directory =="
  rm -rf "$MEM_HOME"
fi

if (( ! NO_TESTS )); then
  echo "== Running unit/integration tests (pytest) =="
  if "$PY_EXE" - <<'PY' 2>/dev/null
import sys
import importlib
sys.exit(0 if importlib.util.find_spec('pytest') else 1)
PY
  then
    "$PY_EXE" -m pytest -q "$ROOT_DIR/tests" || { echo "Tests failed" >&2; exit 1; }
  elif command -v pytest >/dev/null 2>&1; then
    pytest -q "$ROOT_DIR/tests" || { echo "Tests failed" >&2; exit 1; }
  else
    echo "pytest not found; skipping tests. Run: pip install pytest (or use .mcp-venv)"
  fi
else
  echo "== Skipping tests (--no-tests) =="
fi

if (( KILL_PORT )); then
  echo "== Freeing port $PORT if in use =="
  if command -v fuser >/dev/null 2>&1; then
    fuser -k -n tcp "$PORT" 2>/dev/null || true
  elif command -v lsof >/dev/null 2>&1; then
    PIDS=$(lsof -ti tcp:"$PORT" -sTCP:LISTEN || true)
    [ -n "$PIDS" ] && kill $PIDS || true
  else
    echo "  (no fuser/lsof available; skipping kill-port)"
  fi
fi

if (( SMOKE )); then
  echo "== Starting server in background for smoke checks =="
  # shellcheck disable=SC2086
  TS=$(date +%Y%m%d-%H%M%S)
  MEM_LOG_DIR="$LOG_DIR" MEM_LOG_LEVEL="${MEM_LOG_LEVEL:-INFO}" MEM_DEBUG="${MEM_DEBUG:-0}" MEM_LOG_TS=1 \
    bash -lc "cd \"$ROOT_DIR\" && $APP --home \"$MEM_HOME\" ${ARGS[*]}" >"$LOG_DIR/server-bg-$TS.out" 2>&1 &
  BG_PID=$!
  trap 'kill $BG_PID 2>/dev/null || true' EXIT

  echo "== Waiting for /healthz =="
  for i in $(seq 1 40); do
    if curl -fsS "$BASE_URL/healthz" >/dev/null 2>&1; then
      echo "  healthz OK"; break
    fi
    sleep 0.5
  done

  echo "== MCP: initialize + tools/list =="
  AUTH_HEADER=( )
  [ -n "${MEM_TOKEN:-}" ] && AUTH_HEADER=( -H "Authorization: Bearer $MEM_TOKEN" )
  MCP_DISC=$(curl -fsS -H 'Content-Type: application/json' -H 'Accept: application/json' "${AUTH_HEADER[@]}" --data-binary @- "$BASE_URL/mcp" <<JSON || true
[
 {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}},
 {"jsonrpc":"2.0","id":2,"method":"tools/list"}
]
JSON
)
  if echo "$MCP_DISC" | grep -q '"tools"'; then
    echo "  tools/list OK"
  else
    echo "  tools/list FAILED"; echo "$MCP_DISC"; echo "--- server logs ---"; tail -n 200 "$LOG_DIR/server-bg.out" || true; exit 1
  fi

  echo "== MCP: write/read smoke =="
  KEY="smoke_$(date +%s)"
  WRITE=$(curl -fsS -H 'Content-Type: application/json' -H 'Accept: application/json' "${AUTH_HEADER[@]}" --data-binary @- "$BASE_URL/mcp" <<JSON || true
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"write_memory","arguments":{"project":"Smoke","scope":"project","key":"$KEY","text":"hello from smoke"}}}
JSON
)
  if ! echo "$WRITE" | grep -q '"isError":false'; then
    echo "  write_memory FAILED"; echo "$WRITE"; exit 1
  fi
  READ=$(curl -fsS -H 'Content-Type: application/json' -H 'Accept: application/json' "${AUTH_HEADER[@]}" --data-binary @- "$BASE_URL/mcp" <<JSON || true
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"read_memory","arguments":{"project":"Smoke","key":"$KEY"}}}
JSON
)
  if echo "$READ" | grep -q '"text":"hello from smoke"'; then
    echo "  read_memory OK"
  else
    echo "  read_memory FAILED"; echo "$READ"; echo "--- server logs ---"; tail -n 200 "$LOG_DIR/server-bg.out" || true; exit 1
  fi

  echo "== Smoke checks passed =="
  echo "== Restarting in foreground =="
  kill "$BG_PID" 2>/dev/null || true
  trap - EXIT
fi

echo "== Starting Memory-MCP server (Ctrl+C to stop) =="
# shellcheck disable=SC2086
exec env MEM_LOG_DIR="$LOG_DIR" MEM_LOG_LEVEL="${MEM_LOG_LEVEL:-INFO}" MEM_DEBUG="${MEM_DEBUG:-0}" MEM_LOG_TS=1 \
  bash -lc "cd \"$ROOT_DIR\" && $APP --home \"$MEM_HOME\" ${ARGS[*]}"
