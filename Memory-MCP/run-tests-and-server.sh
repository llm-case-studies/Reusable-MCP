#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP="python3 \"$ROOT_DIR/server/app.py\""
HOME_DIR_DEFAULT="$HOME/.roadnerd/memorydb"
MEM_HOME="${MEM_HOME:-$HOME_DIR_DEFAULT}"

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

echo "== Memory-MCP: settings =="
echo "  MEM_HOME=$MEM_HOME"
echo "  HOST=$HOST PORT=$PORT"
echo "  flags: no-tests=$NO_TESTS clean-home=$CLEAN_HOME kill-port=$KILL_PORT smoke=$SMOKE"

if (( CLEAN_HOME )); then
  echo "== Cleaning home directory =="
  rm -rf "$MEM_HOME"
fi

if (( ! NO_TESTS )); then
  echo "== Running unit/integration tests (pytest) =="
  if command -v pytest >/dev/null 2>&1; then
    pytest -q "$ROOT_DIR/tests" || { echo "Tests failed" >&2; exit 1; }
  else
    echo "pytest not found; skipping tests. Run: pip install pytest"
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
  bash -lc "$APP --home \"$MEM_HOME\" ${ARGS[*]}" >/tmp/memory-mcp.out 2>&1 &
  BG_PID=$!
  trap 'kill $BG_PID 2>/dev/null || true' EXIT

  echo "== Waiting for /healthz =="
  for i in {1..30}; do
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
    echo "  tools/list FAILED"; echo "$MCP_DISC"; exit 1
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
    echo "  read_memory FAILED"; echo "$READ"; exit 1
  fi

  echo "== Smoke checks passed =="
  echo "== Restarting in foreground =="
  kill "$BG_PID" 2>/dev/null || true
  trap - EXIT
fi

echo "== Starting Memory-MCP server (Ctrl+C to stop) =="
# shellcheck disable=SC2086
exec bash -lc "$APP --home \"$MEM_HOME\" ${ARGS[*]}"
