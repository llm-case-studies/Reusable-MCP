#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "== Reusable-MCP: shared venv setup =="
VENV="$REPO_ROOT/.venv"
if [ -d "$VENV" ]; then
  echo "  venv exists: $VENV"
else
  echo "  creating venv: $VENV"
  python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"
echo "  using python: $(command -v python)"

echo "== Installing Python deps (fastapi, uvicorn, pytest) =="
pip install -U pip >/dev/null
pip install fastapi uvicorn pytest >/dev/null

echo "== Optional: install Memory-MCP package for console script =="
echo "   (skip by default to keep editable dev; run manually if desired)"
echo "   pip install ./Memory-MCP"

echo "== Checking external tools =="
if [ -x /usr/bin/rg ]; then
  echo "  ripgrep: OK (/usr/bin/rg)"
else
  echo "  ripgrep: MISSING (required for Code-Log-Search). Install e.g.: sudo apt install ripgrep"
fi

echo "== Summary =="
python - <<'PY'
import sys
import importlib
mods = ["fastapi","uvicorn","pytest"]
for m in mods:
    try:
        v = importlib.import_module(m).__version__
    except Exception:
        v = "not-installed"
    print(f"  {m}: {v}")
print(f"  python: {sys.executable}")
PY

echo "\nNext steps:"
echo "  - Activate venv: source $VENV/bin/activate"
echo "  - Start Memory:  MEM_TOKEN=secret memory-mcp --home ~/.roadnerd/memorydb --host 127.0.0.1 --port 7090" || true
echo "  - Start Code-Log: ./Code-Log-Search-MCP/run-tests-and-server.sh --kill-port --smoke --host 127.0.0.1 --port 7080 --default-code-root \"$PWD\" --logs-root \"$HOME/.roadnerd/logs\""

