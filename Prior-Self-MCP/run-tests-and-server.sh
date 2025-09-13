#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"

# Python selection: prefer repo .venv, then service .mcp-venv, then system
REPO_VENV_PY="$REPO_ROOT/.venv/bin/python"
SVC_VENV_PY="$ROOT_DIR/.mcp-venv/bin/python"
if [ -x "$REPO_VENV_PY" ]; then
  PY_EXE="$REPO_VENV_PY"
elif [ -x "$SVC_VENV_PY" ]; then
  PY_EXE="$SVC_VENV_PY"
else
  PY_EXE="python3"
fi
APP="$PY_EXE -m server.app"

# Defaults (editable). .env in this folder can override these.
DEFAULT_HOST="${HOST:-127.0.0.1}"
DEFAULT_PORT="${PORT:-7070}"
DEFAULT_HOME="${PRIOR_SELF_HOME:-$HOME/.roadnerd/chatdb}"
DEFAULT_NO_TESTS="${NO_TESTS:-0}"
DEFAULT_KILL_PORT="${KILL_PORT:-1}"
DEFAULT_SMOKE="${SMOKE:-1}"
DEFAULT_PRIOR_TOKEN="${PRIOR_TOKEN:-}"

if [ -f "$ROOT_DIR/.env" ]; then
  # shellcheck disable=SC1090
  source "$ROOT_DIR/.env"
  DEFAULT_HOST="${HOST:-$DEFAULT_HOST}"
  DEFAULT_PORT="${PORT:-$DEFAULT_PORT}"
  DEFAULT_HOME="${PRIOR_SELF_HOME:-$DEFAULT_HOME}"
  DEFAULT_NO_TESTS="${NO_TESTS:-$DEFAULT_NO_TESTS}"
  DEFAULT_KILL_PORT="${KILL_PORT:-$DEFAULT_KILL_PORT}"
  DEFAULT_SMOKE="${SMOKE:-$DEFAULT_SMOKE}"
  DEFAULT_PRIOR_TOKEN="${PRIOR_TOKEN:-$DEFAULT_PRIOR_TOKEN}"
fi

NO_TESTS="$DEFAULT_NO_TESTS"
KILL_PORT="$DEFAULT_KILL_PORT"
SMOKE="$DEFAULT_SMOKE"
HOST="$DEFAULT_HOST"
PORT="$DEFAULT_PORT"
HOME_DIR="$DEFAULT_HOME"

ARGS=( )
while (("$#")); do
  case "$1" in
    -h|--help)
      cat <<USAGE
Prior-Self-MCP dev runner

Usage: ./run-tests-and-server.sh [options]

Config (edit script or .env):
  HOST=$HOST PORT=$PORT PRIOR_SELF_HOME=$HOME_DIR NO_TESTS=$NO_TESTS KILL_PORT=$KILL_PORT SMOKE=$SMOKE

Options:
  --no-tests        Skip pytest
  --kill-port       Free the port before start
  --smoke           Seed transcripts, build index, healthz + MCP init/list + search_previous_chats
  --host <addr>     Bind host (default $HOST)
  --port <num>      Bind port (default $PORT)
  --home <path>     Data home (default $HOME_DIR)
  -h, --help        Show this help
USAGE
      exit 0 ;;
    --no-tests) NO_TESTS=1; shift ;;
    --kill-port) KILL_PORT=1; shift ;;
    --smoke) SMOKE=1; shift ;;
    --host) HOST="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --port) PORT="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --home) HOME_DIR="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --host=*|--port=*|--home=*)
      KEY="${1%%=*}"; VAL="${1#*=}"; case "$KEY" in
        --host) HOST="$VAL" ;;
        --port) PORT="$VAL" ;;
        --home) HOME_DIR="$VAL" ;;
      esac; ARGS+=("$1"); shift ;;
    *) ARGS+=("$1"); shift ;;
  esac
done

echo "== Prior-Self-MCP: settings =="
echo "  PY_EXE=$PY_EXE ($(command -v "$PY_EXE" || echo not-found))"
echo "  HOME=$HOME_DIR"
echo "  HOST=$HOST PORT=$PORT"
echo "  flags: no-tests=$NO_TESTS kill-port=$KILL_PORT smoke=$SMOKE"

mkdir -p "$HOME_DIR/transcripts"

if (( ! NO_TESTS )); then
  echo "== Running tests (pytest) =="
  if "$PY_EXE" - <<'PY' 2>/dev/null
import sys, importlib
sys.exit(0 if importlib.util.find_spec('pytest') else 1)
PY
  then
    "$PY_EXE" -m pytest -q "$ROOT_DIR/tests" || { echo "Tests failed" >&2; exit 1; }
  elif command -v pytest >/dev/null 2>&1; then
    pytest -q "$ROOT_DIR/tests" || { echo "Tests failed" >&2; exit 1; }
  else
    echo "pytest not found; skipping tests. Install with: pip install pytest"
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
  fi
fi

if (( SMOKE )); then
  echo "== Seeding transcripts and building index =="
  printf '%s\n' '{"chat_id":"s1","project":"Smoke","ts":"2025-01-01T00:00:00","role":"assistant","text":"tokens brainstorm"}' > "$HOME_DIR/transcripts/Smoke.jsonl"
  "$PY_EXE" "$ROOT_DIR/indexer/build_index.py" --home "$HOME_DIR"

  echo "== Starting server in background for smoke checks =="
  TS=$(date +%Y%m%d-%H%M%S)
  bash -lc "cd \"$ROOT_DIR\" && $APP --home \"$HOME_DIR\" --host \"$HOST\" --port \"$PORT\"" >"$ROOT_DIR/server-bg-$TS.out" 2>&1 &
  BG_PID=$!
  trap 'kill $BG_PID 2>/dev/null || true' EXIT

  BASE_URL="http://$HOST:$PORT"
  echo "== Waiting for /healthz =="
  READY=0
  for i in $(seq 1 40); do
    if curl -fsS "$BASE_URL/healthz" >/dev/null 2>&1; then echo "  healthz OK"; READY=1; break; fi
    sleep 0.5
  done
  if [ "$READY" -ne 1 ]; then
    echo "ERROR: healthz did not become ready" >&2
    tail -n 200 "$ROOT_DIR/server-bg-$TS.out" >&2 || true
    exit 1
  fi

  echo "== MCP: initialize + tools/list + search_previous_chats =="
  AUTH_HEADER=( )
  if [ -n "${PRIOR_TOKEN:-$DEFAULT_PRIOR_TOKEN}" ]; then
    AUTH_HEADER=( -H "Authorization: Bearer ${PRIOR_TOKEN:-$DEFAULT_PRIOR_TOKEN}" )
  fi
  INIT=$(curl -fsS -H 'Content-Type: application/json' -H 'Accept: application/json' "${AUTH_HEADER[@]}" --data-binary @- "$BASE_URL/mcp" <<JSON || true
[{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}},{"jsonrpc":"2.0","id":2,"method":"tools/list"}]
JSON
)
  echo "$INIT" | grep -q '"tools"' || { echo "tools/list FAILED"; echo "$INIT"; exit 1; }
  CALL=$(curl -fsS -H 'Content-Type: application/json' -H 'Accept: application/json' "${AUTH_HEADER[@]}" --data-binary @- "$BASE_URL/mcp" <<JSON || true
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_previous_chats","arguments":{"query":"tokens","project":"Smoke","k":5}}}
JSON
)
  echo "$CALL" | grep -q 'structuredContent' && echo "  search_previous_chats OK" || { echo "  search_previous_chats FAILED"; echo "$CALL"; exit 1; }

  echo "== Smoke passed; restarting in foreground =="
  kill "$BG_PID" 2>/dev/null || true
  trap - EXIT
fi

echo "== Starting Prior-Self-MCP server (Ctrl+C to stop) =="
exec bash -lc "cd \"$ROOT_DIR\" && $APP --home \"$HOME_DIR\" --host \"$HOST\" --port \"$PORT\""

