#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "== Reusable-MCP: dev environment check =="
if [ -d .venv ]; then
  echo "  shared venv: $REPO_ROOT/.venv"
  source .venv/bin/activate
  echo "  python: $(command -v python)"
else
  echo "  shared venv: NOT FOUND (.venv). Run scripts/dev-setup.sh"
fi

echo "== Python deps =="
python - <<'PY'
import importlib
for m in ["fastapi","uvicorn","pytest"]:
    try:
        print(f"  {m}: "+importlib.import_module(m).__version__)
    except Exception:
        print(f"  {m}: not-installed")
PY

echo "== External tools =="
if [ -x /usr/bin/rg ]; then
  echo "  ripgrep: OK (/usr/bin/rg)"
else
  echo "  ripgrep: MISSING (required for Code-Log-Search)"
fi

echo "== Ports =="
for p in 7070 7080 7090; do
  if ss -ltnp 2>/dev/null | rg ":$p\b" >/dev/null; then
    echo "  port $p: LISTENING"
  else
    echo "  port $p: free"
  fi
done

echo "== Gemini config =="
if [ -f .gemini/settings.json ]; then
  echo "  .gemini/settings.json present"
  rg -n 'code-log-search|memory-mcp|prior-self' .gemini/settings.json || true
else
  echo "  .gemini/settings.json not found"
fi

echo "== Tips =="
echo "  - Start Memory:  MEM_TOKEN=secret memory-mcp --home ~/.roadnerd/memorydb --host 127.0.0.1 --port 7090"
echo "  - Start Code-Log: ./Code-Log-Search-MCP/run-tests-and-server.sh --kill-port --smoke --host 127.0.0.1 --port 7080 --default-code-root \"$PWD\" --logs-root \"$HOME/.roadnerd/logs\""
echo "  - Start Prior-Self: python3 Prior-Self-MCP/server/app.py --home \"$HOME/.roadnerd/chatdb\" --host 127.0.0.1 --port 7070"

