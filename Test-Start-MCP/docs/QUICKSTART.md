Test‑Start‑MCP — Quickstart

One venv per repo (auto‑used by runners)
- Create once if needed: `python3 -m venv .venv && source .venv/bin/activate && pip install -U pip fastapi uvicorn pytest`
- Runners discover `./.venv/bin/python` automatically; activation is optional.

Run
- `./Test-Start-MCP/run-tests-and-server.sh` (runs tests if pytest installed, then starts on :7060)
- Or: `python3 Test-Start-MCP/server/app.py --host 127.0.0.1 --port 7060`

Endpoints
- REST: `POST /actions/run_script`, `POST /actions/list_allowed`
- SSE: `GET /sse/run_script_stream`
- MCP: `POST /mcp` (JSON‑RPC over HTTP)
- Health: `GET /healthz`

Auth
- Optional bearer token via `TSM_TOKEN`. If set, all endpoints (incl. SSE, MCP) require `Authorization: Bearer <token>`.

Config (env)
- `TSM_ALLOWED_ROOT`, `TSM_ALLOWED_SCRIPTS`, `TSM_ALLOWED_ARGS`, `TSM_ENV_ALLOWLIST`
- `TSM_TIMEOUT_MS_DEFAULT=90000`, `TSM_MAX_OUTPUT_BYTES=262144`, `TSM_MAX_LINE_BYTES=8192`
- `TSM_LOG_DIR=Test-Start-MCP/logs`, `TSM_LOG_LEVEL=INFO|DEBUG`

MCP (examples)
```
# initialize
curl -sS -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}' \
  http://127.0.0.1:7060/mcp | jq .

# tools/list
curl -sS -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  http://127.0.0.1:7060/mcp | jq .

# run_script (example)
curl -sS -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"run_script","arguments":{"path":"/home/alex/Projects/Reusable-MCP/Code-Log-Search-MCP/run-tests-and-server.sh","args":["--kill-port","--smoke"],"timeout_ms":90000}}}' \
  http://127.0.0.1:7060/mcp | jq .

# SSE stream (stdout/stderr/events)
curl -N "http://127.0.0.1:7060/sse/run_script_stream?path=/home/alex/Projects/Reusable-MCP/Code-Log-Search-MCP/run-tests-and-server.sh&args=--kill-port,--smoke&timeout_ms=90000"
```
