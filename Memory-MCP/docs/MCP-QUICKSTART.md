Memory‑MCP — MCP Quickstart

Overview
- HTTP actions: `/actions/write_memory`, `/actions/read_memory`, `/actions/search_memory`, `/actions/list_memories`
- SSE: `/sse/stream_search_memory`
- MCP (Streamable HTTP JSON‑RPC): single endpoint `/mcp` with `initialize`, `tools/list`, `tools/call`.

Install (local)
- Python 3.10+
- In repo root:
  - `cd Memory-MCP`
  - `python3 -m venv .venv && source .venv/bin/activate`
  - `pip install -U pip && pip install .`

Run
- `MEM_TOKEN=secret memory-mcp --home ~/.roadnerd/memorydb --host 127.0.0.1 --port 7090`

Auth
- Optional bearer token via `MEM_TOKEN`. If set, include `Authorization: Bearer <token>` on all requests.

MCP JSON‑RPC (curl)
1) Initialize
```
curl -sS \
  -H 'Accept: application/json' \
  -H "Authorization: Bearer $MEM_TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}' \
  http://127.0.0.1:7090/mcp | jq .
```
2) Tools list
```
curl -sS \
  -H 'Accept: application/json' \
  -H "Authorization: Bearer $MEM_TOKEN" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  http://127.0.0.1:7090/mcp | jq .
```
3) Call tool
```
curl -sS \
  -H 'Accept: application/json' \
  -H "Authorization: Bearer $MEM_TOKEN" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"write_memory","arguments":{"project":"RoadNerd","scope":"project","key":"policy","text":"Example from curl","tags":["test"]}}}' \
  http://127.0.0.1:7090/mcp | jq .
```

Python JSON‑RPC example
See `../examples/mcp_client.py` for a minimal client that runs initialize → tools/list → tools/call.

Docker (dev)
1) Build: `docker build -t memory-mcp:dev ./Memory-MCP`
2) Run: `docker run --rm -e MEM_TOKEN=secret -p 7090:7090 memory-mcp:dev`

Observability and limits
- Logging: `MEM_LOG_DIR`, `MEM_LOG_FILE`, `MEM_LOG_LEVEL`, `MEM_DEBUG`, `MEM_LOG_ROTATE`, `MEM_LOG_BACKUPS`.
- Concurrency (optional pattern): cap requests via proxy or orchestrator; future services will honor `*_CONCURRENT_REQUESTS`.
- Map Addition‑1 config to envs (pattern to reuse across MCPs):
  - `*_TIMEOUT_MS`, `*_ALLOWLIST`, `*_MAX_*`, `*_USER_AGENT`.

Troubleshooting
- 401 Unauthorized → set `MEM_TOKEN` in server and send `Authorization` header.
- Port in use → change `--port` or stop conflicting process.
- JSON‑RPC errors → check `method` and tool `name`; protocol errors return JSON‑RPC `error`, tool errors set `isError: true` in `result`.

