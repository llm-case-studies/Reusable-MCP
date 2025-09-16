Test‑Start‑MCP — Quickstart

One venv per repo (auto‑used by runners)
- Create once if needed: `python3 -m venv .venv && source .venv/bin/activate && pip install -U pip fastapi uvicorn pytest`
- Runners discover `./.venv/bin/python` automatically; activation is optional.

Run
- `./Test-Start-MCP/run-tests-and-server.sh` (runs tests if pytest installed, frees the port, then starts on `TSM_HOST:TSM_PORT`)
- Defaults: `TSM_HOST=127.0.0.1`, `TSM_PORT=7060` — override via env
- Or: `python3 Test-Start-MCP/server/app.py --host 127.0.0.1 --port 7060`

Endpoints
- UI: `GET /start` (interactive UI), `GET /mcp_ui` (MCP playground)
- REST: `POST /actions/run_script`, `POST /actions/list_allowed`, `POST /actions/search_logs`, `POST /actions/get_stats`
- SSE: `GET /sse/run_script_stream`, `GET /sse/logs_stream`
- MCP: `POST /mcp` (JSON‑RPC over HTTP)
- Health: `GET /healthz`
 - Admin: `GET /admin`, `GET /admin/new`, `GET /admin/state`, `POST /admin/allowlist/add`, `POST /admin/allowlist/remove`, `POST /admin/session/profile`

Auth
- Optional bearer token via `TSM_TOKEN`. If set, all endpoints (incl. SSE, MCP) require `Authorization: Bearer <token>`.
 - Admin endpoints require `TSM_ADMIN_TOKEN` via `Authorization: Bearer <admin-token>`.

Config (env)
- `TSM_ALLOWED_ROOT`, `TSM_ALLOWED_SCRIPTS`, `TSM_ALLOWED_ARGS`, `TSM_ENV_ALLOWLIST`
- `TSM_TIMEOUT_MS_DEFAULT=90000`, `TSM_MAX_OUTPUT_BYTES=262144`, `TSM_MAX_LINE_BYTES=8192`
- `TSM_LOG_DIR=Test-Start-MCP/logs`, `TSM_LOG_LEVEL=INFO|DEBUG`
- Admin/policy: `TSM_ADMIN_TOKEN`, `TSM_ALLOWED_FILE` (defaults to `Test-Start-MCP/allowlist.json`)
 - Preflight: `TSM_REQUIRE_PREFLIGHT=0|1`, `TSM_PREFLIGHT_TTL_SEC=600`

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

Admin & Pre‑flight
- Recommended workflow: perform a pre‑flight check before running any script; then configure policy in the Admin UI if needed.
- See Admin/Pre‑flight spec: `Test-Start-MCP/docs/ADMIN-PREFLIGHT-SPEC.md`.
- Step‑by‑step walkthrough (UI + Admin): `Test-Start-MCP/docs/E2E-TUTORIAL.md`.
- Highlights:
  - New tool/endpoint (check_script) to verify allow status and get an admin link + suggestions.
  - Admin UI (token‑protected) to add TTL‑bound rules by path or scope+patterns, or assign session profiles (tester/reviewer/developer/architect).
  - Optional enforcement: `TSM_REQUIRE_PREFLIGHT=1` to force a successful preflight first in a session. Provide a session via header `X-TSM-Session` for REST/SSE/MCP.
  - Policy audit entries: `policy-YYYYMMDD.jsonl` under `TSM_LOG_DIR` for add/remove/overlay actions.
