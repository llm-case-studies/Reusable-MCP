MCP Dev Pattern — Runtime, Venvs, Endpoints, Logging

Overview
- All MCP servers in this repo follow the same shape:
  - REST actions under `/actions/*`
  - Optional SSE under `/sse/*`
  - Streamable HTTP MCP endpoint at `POST /mcp` with `initialize`, `tools/list`, `tools/call`
  - Dev pages: `/docs` (Swagger), `/redoc`, and `/mcp_ui` (HTML MCP playground)
- Each server supports optional Bearer token auth via an env var, and common logging env vars.

Python environments (venvs)
- Recommended: one shared venv at repo root so all MCPs use the same interpreter and deps.
  - Create once:
    - `python3 -m venv .venv && source .venv/bin/activate`
    - `pip install -U pip fastapi uvicorn pytest`
    - Optional (for console script): `pip install ./Memory-MCP` → adds `memory-mcp`
  - Verify which Python: `python -c 'import sys; print(sys.executable)'` → should print `<repo>/.venv/bin/python`
- Runners’ resolution order:
  - If a service-local venv exists at `<service>/.mcp-venv`, the runner uses that.
  - Otherwise it uses the active `python3` (so, if you’ve activated `<repo>/.venv`, both servers share it).
  - We did not create any `.mcp-venv` by default; using a shared `.venv` is the simple path.

Auth & Ports
- Tokens (optional):
  - Memory: `MEM_TOKEN`
  - Code-Log-Search: `CLS_TOKEN`
  - Prior-Self: `PRIOR_TOKEN` (or `PRIOR_SELF_TOKEN`)
- Default ports:
  - Memory: 7090
  - Code-Log-Search: 7080
  - Prior-Self: 7070

Logging env vars (common pattern)
- `<PREFIX>_LOG_LEVEL=INFO|DEBUG|...`
- `<PREFIX>_LOG_DIR=<dir>` or `<PREFIX>_LOG_FILE=<file>` (with `<PREFIX>_LOG_TS=1` to timestamp filenames)
- Rotation: `<PREFIX>_LOG_ROTATE=<bytes>`, `<PREFIX>_LOG_BACKUPS=<n>`
- Prefixes: `MEM`, `CLS`, `PRIOR`

Endpoints (standard)
- Health: `GET /healthz`
- Actions: `POST /actions/<tool>` (typed JSON in/out)
- SSE: `GET /sse/<stream>` (events: `ping`, `message`, `end`, `error`)
- MCP: `POST /mcp` (JSON‑RPC 2.0)
- Dev pages:
  - Swagger: `/docs` and `/redoc`
  - MCP UI: `/mcp_ui` (initialize, list, call)
  - Service UIs: Memory `/mem`; Code‑Log‑Search `/search`

Run scripts
- Memory‑MCP: `Memory-MCP/run-tests-and-server.sh`
  - Flags: `--no-tests`, `--clean-home`, `--kill-port`, `--smoke`, `--host`, `--port`
- Code‑Log‑Search‑MCP: `Code-Log-Search-MCP/run-tests-and-server.sh`
  - Flags: `--no-tests`, `--kill-port`, `--smoke`, `--host`, `--port`, `--default-code-root`, `--logs-root`
- Both:
  - Use `<service>/.mcp-venv/bin/python` if present; else `python3` (your active venv)
  - `--smoke` runs a short MCP flow before serving

Service‑specific notes
- Memory‑MCP: console script `memory-mcp` available when package installed into your venv.
- Code‑Log‑Search‑MCP: requires the `ripgrep` binary at `/usr/bin/rg`.
- Prior‑Self‑MCP: build the index first via `Prior-Self-MCP/indexer/build_index.py`.
- Test‑Start‑MCP (scaffold): new service to run allowlisted dev scripts (e.g., runners) under strict policy when models’ sandboxes can’t execute scripts.

Gemini CLI
- Repo config: `.gemini/settings.json` includes HTTP URLs for all servers and workspace mappings.
- Start servers, then run `gemini mcp list` to confirm readiness.

Quick commands (shared venv)
- Create/activate shared venv: `python3 -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -U pip fastapi uvicorn pytest`
- Memory: `MEM_TOKEN=secret memory-mcp --home ~/.roadnerd/memorydb --host 127.0.0.1 --port 7090`
- Code‑Log‑Search: `./Code-Log-Search-MCP/run-tests-and-server.sh --kill-port --smoke --host 127.0.0.1 --port 7080 --default-code-root "$PWD" --logs-root "$HOME/.roadnerd/logs"`
- Prior‑Self: `python3 Prior-Self-MCP/server/app.py --home "$HOME/.roadnerd/chatdb" --host 127.0.0.1 --port 7070`
- Test‑Start: scaffold only; see `Test-Start-MCP/docs/SPEC.md` for upcoming APIs.
