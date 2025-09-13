#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Detect available pythons: prefer repo-level .venv first, then service .mcp-venv, then system python3
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
REPO_VENV_PY="$REPO_ROOT/.venv/bin/python"
SVC_VENV_PY="$ROOT_DIR/.mcp-venv/bin/python"

echo "== Python environments (detected) =="
if [ -x "$REPO_VENV_PY" ]; then echo "  repo venv: $REPO_VENV_PY"; else echo "  repo venv: (not found) $REPO_ROOT/.venv"; fi
if [ -x "$SVC_VENV_PY" ]; then echo "  service venv: $SVC_VENV_PY"; else echo "  service venv: (not found) $ROOT_DIR/.mcp-venv"; fi
echo "  system python3: $(command -v python3 || echo not-found)"

if [ -x "$REPO_VENV_PY" ]; then
  PY_EXE="$REPO_VENV_PY"
elif [ -x "$SVC_VENV_PY" ]; then
  PY_EXE="$SVC_VENV_PY"
else
  PY_EXE="python3"
fi
echo "== Using python: $PY_EXE"
APP="$PY_EXE -m server.app"

# ------------------------------------
# Config (edit these for your defaults)
# You can also override any of these via environment variables
# or via CLI flags (flags take precedence).
# ------------------------------------
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
DEFAULT_HOST="${HOST:-127.0.0.1}"
DEFAULT_PORT="${PORT:-7080}"
# Default to repo root for code, can override with CLS_CODE_ROOT env or flag
DEFAULT_CODE_ROOT="${CLS_CODE_ROOT:-$REPO_ROOT}"
# Keep logs inside this service folder by default (handy for dev)
DEFAULT_LOGS_ROOT="${RN_LOG_DIR:-$ROOT_DIR/logs}"
DEFAULT_NO_TESTS="${NO_TESTS:-0}"
DEFAULT_KILL_PORT="${KILL_PORT:-1}"
DEFAULT_SMOKE="${SMOKE:-1}"
# Optional token passed to Authorization header during smoke
DEFAULT_CLS_TOKEN="${CLS_TOKEN:-}"

# If present, allow a dotenv-style file to override the defaults above
if [ -f "$ROOT_DIR/.env" ]; then
  # shellcheck disable=SC1090
  source "$ROOT_DIR/.env"
  DEFAULT_HOST="${HOST:-$DEFAULT_HOST}"
  DEFAULT_PORT="${PORT:-$DEFAULT_PORT}"
  DEFAULT_CODE_ROOT="${CLS_CODE_ROOT:-$DEFAULT_CODE_ROOT}"
  DEFAULT_LOGS_ROOT="${RN_LOG_DIR:-$DEFAULT_LOGS_ROOT}"
  DEFAULT_NO_TESTS="${NO_TESTS:-$DEFAULT_NO_TESTS}"
  DEFAULT_KILL_PORT="${KILL_PORT:-$DEFAULT_KILL_PORT}"
  DEFAULT_SMOKE="${SMOKE:-$DEFAULT_SMOKE}"
  DEFAULT_CLS_TOKEN="${CLS_TOKEN:-$DEFAULT_CLS_TOKEN}"
fi

LOG_DIR="$ROOT_DIR/logs"

NO_TESTS="$DEFAULT_NO_TESTS"
KILL_PORT="$DEFAULT_KILL_PORT"
SMOKE="$DEFAULT_SMOKE"

HOST="$DEFAULT_HOST"
PORT="$DEFAULT_PORT"
CODE_ROOT="$DEFAULT_CODE_ROOT"
LOGS_ROOT="$DEFAULT_LOGS_ROOT"

ARGS=( )
while (("$#")); do
  case "$1" in
    -h|--help)
      cat <<USAGE
Code-Log-Search-MCP dev runner

Usage:
  ./run-tests-and-server.sh [options]

Description:
  - Detects Python venvs (repo .venv preferred), checks deps (fastapi, uvicorn, ripgrep)
  - Runs tests (pytest) unless --no-tests
  - Optionally frees port (--kill-port) and runs a smoke flow (--smoke)
  - Starts the server in the foreground with logging to Code-Log-Search-MCP/logs

Config (edit top of script or use .env in this folder):
  HOST=$DEFAULT_HOST  PORT=$DEFAULT_PORT
  CODE_ROOT=$DEFAULT_CODE_ROOT
  LOGS_ROOT=$DEFAULT_LOGS_ROOT
  NO_TESTS=$DEFAULT_NO_TESTS  KILL_PORT=$DEFAULT_KILL_PORT  SMOKE=$DEFAULT_SMOKE
  CLS_TOKEN=(used only for smoke Authorization header when set)

Options (flags override config):
  --no-tests                  Skip running pytest
  --kill-port                 Free the port before starting
  --smoke                     Run smoke (healthz, MCP init/list, search_code, search_logs)
  --host <addr>               Bind host (default: $DEFAULT_HOST)
  --port <num>                Bind port (default: $DEFAULT_PORT)
  --default-code-root <path>  Code root directory (default: $DEFAULT_CODE_ROOT)
  --logs-root <path>          Logs root directory (default: $DEFAULT_LOGS_ROOT)
  -h, --help                  Show this help and exit

Examples:
  ./run-tests-and-server.sh
  ./run-tests-and-server.sh --no-tests --kill-port
  HOST=0.0.0.0 PORT=7080 ./run-tests-and-server.sh
  (or create Code-Log-Search-MCP/.env with HOST/PORT/CODE_ROOT/LOGS_ROOT)
USAGE
      exit 0
      ;;
    --no-tests) NO_TESTS=1; shift ;;
    --kill-port) KILL_PORT=1; shift ;;
    --smoke) SMOKE=1; shift ;;
    --host) HOST="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --port) PORT="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --default-code-root) CODE_ROOT="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --logs-root) LOGS_ROOT="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --host=*|--port=*|--default-code-root=*|--logs-root=*)
      KEY="${1%%=*}"; VAL="${1#*=}"; case "$KEY" in
        --host) HOST="$VAL" ;;
        --port) PORT="$VAL" ;;
        --default-code-root) CODE_ROOT="$VAL" ;;
        --logs-root) LOGS_ROOT="$VAL" ;;
      esac; ARGS+=("$1"); shift ;;
    *) ARGS+=("$1"); shift ;;
  esac
done

BASE_URL="http://$HOST:$PORT"
mkdir -p "$LOG_DIR" "$LOGS_ROOT"

echo "== Code-Log-Search-MCP: settings =="
echo "  PY_EXE=$PY_EXE ($(command -v "$PY_EXE" || echo not-found))"
echo "  CODE_ROOT=$CODE_ROOT"
echo "  LOGS_ROOT=$LOGS_ROOT"
echo "  HOST=$HOST PORT=$PORT"
echo "  flags: no-tests=$NO_TESTS kill-port=$KILL_PORT smoke=$SMOKE"
if [ -n "$DEFAULT_CLS_TOKEN" ]; then echo "  auth: CLS_TOKEN is set (used for smoke)"; fi

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
    echo "pytest not found; skipping tests. Hint: source .venv/bin/activate && pip install pytest (or run scripts/dev-setup.sh)"
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

## Dependency checks before smoke/start
# Check Python deps: fastapi + uvicorn (import test)
if ! "$PY_EXE" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
  echo "ERROR: Python deps missing for server (need fastapi, uvicorn)." >&2
  echo "       Tip: source .venv/bin/activate && pip install -U pip fastapi uvicorn (or run scripts/dev-setup.sh)" >&2
  echo "       Using python: $PY_EXE" >&2
  exit 2
else
  echo "== Python deps OK =="
  "$PY_EXE" - <<'PY'
import fastapi, uvicorn
print(f"  fastapi: {fastapi.__version__}")
print(f"  uvicorn: {uvicorn.__version__}")
PY
fi
# Check ripgrep for search_code
if [ ! -x /usr/bin/rg ]; then
  echo "ERROR: ripgrep not found at /usr/bin/rg (required for search_code)." >&2
  echo "       Install with your package manager, e.g.: sudo apt install ripgrep" >&2
  exit 2
fi

if (( SMOKE )); then
  echo "== Starting server in background for smoke checks =="
  TS=$(date +%Y%m%d-%H%M%S)
  CLS_LOG_DIR="$LOG_DIR" CLS_LOG_LEVEL="${CLS_LOG_LEVEL:-INFO}" CLS_LOG_TS=1 \
    bash -lc "cd \"$ROOT_DIR\" && $APP --host \"$HOST\" --port \"$PORT\" --default-code-root \"$CODE_ROOT\" --logs-root \"$LOGS_ROOT\"" >"$LOG_DIR/server-bg-$TS.out" 2>&1 &
  BG_PID=$!
  trap 'kill $BG_PID 2>/dev/null || true' EXIT

  echo "== Waiting for /healthz =="
  READY=0
  for i in $(seq 1 40); do
    if curl -fsS "$BASE_URL/healthz" >/dev/null 2>&1; then echo "  healthz OK"; READY=1; break; fi
    sleep 0.5
  done
  if [ "$READY" -ne 1 ]; then
    echo "ERROR: healthz did not become ready on $BASE_URL/healthz" >&2
    echo "--- recent server output ---" >&2
    tail -n 200 "$LOG_DIR/server-bg-$TS.out" >&2 || true
    exit 1
  fi

  echo "== MCP: initialize + tools/list =="
  AUTH_HEADER=( )
  if [ -n "${CLS_TOKEN:-$DEFAULT_CLS_TOKEN}" ]; then
    AUTH_HEADER=( -H "Authorization: Bearer ${CLS_TOKEN:-$DEFAULT_CLS_TOKEN}" )
  fi
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

  echo "== MCP: search_code smoke =="
  CALL=$(curl -fsS -H 'Content-Type: application/json' -H 'Accept: application/json' "${AUTH_HEADER[@]}" --data-binary @- "$BASE_URL/mcp" <<JSON || true
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_code","arguments":{"query":"README|MCP","root":"$CODE_ROOT","maxResults":5,"contextLines":0}}}
JSON
)
  if echo "$CALL" | grep -q '"structuredContent"'; then
    echo "  search_code OK"
  else
    echo "  search_code FAILED"; echo "$CALL"; exit 1
  fi

  echo "== Preparing logs for search_logs smoke =="
  echo '{"mode":"brainstorm","msg":"ok"}' > "$LOGS_ROOT/20250101.jsonl"
  CALL2=$(curl -fsS -H 'Content-Type: application/json' -H 'Accept: application/json' "${AUTH_HEADER[@]}" --data-binary @- "$BASE_URL/mcp" <<JSON || true
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"search_logs","arguments":{"query":"brainstorm","date":"20250101","mode":"brainstorm","maxResults":5}}}
JSON
)
  if echo "$CALL2" | grep -q '"structuredContent"'; then
    echo "  search_logs OK"
  else
    echo "  search_logs FAILED"; echo "$CALL2"; exit 1
  fi

  echo "== Smoke checks passed =="
  echo "== Restarting in foreground =="
  kill "$BG_PID" 2>/dev/null || true
  trap - EXIT
fi

echo "== Starting Code-Log-Search-MCP server (Ctrl+C to stop) =="
exec env CLS_LOG_DIR="$LOG_DIR" CLS_LOG_LEVEL="${CLS_LOG_LEVEL:-INFO}" CLS_LOG_TS=1 \
  bash -lc "cd \"$ROOT_DIR\" && $APP --host \"$HOST\" --port \"$PORT\" --default-code-root \"$CODE_ROOT\" --logs-root \"$LOGS_ROOT\""
