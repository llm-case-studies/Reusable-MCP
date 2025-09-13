Test‑Start‑MCP — Quickstart (Scaffold)

Status: Not implemented yet. This page describes intended usage once implemented.

Endpoints
- REST: `POST /actions/run_script`, `POST /actions/list_allowed`
- SSE: `GET /sse/run_script_stream`
- Health: `GET /healthz`

Auth
- Optional bearer token via `TSM_TOKEN`. If set, all endpoints and SSE require `Authorization: Bearer <token>`.

Config (env)
- `TSM_ALLOWED_ROOT`, `TSM_ALLOWED_SCRIPTS`, `TSM_ALLOWED_ARGS`, `TSM_ENV_ALLOWLIST`
- `TSM_TIMEOUT_MS_DEFAULT=90000`, `TSM_LOG_DIR=Test-Start-MCP/logs`

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
```

