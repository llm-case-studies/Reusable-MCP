# Memory‑MCP

A small, reusable HTTP/SSE MCP service that provides durable, project‑scoped memory for agents.

- Transport: HTTP + SSE (no stdio)
- Storage: SQLite + FTS (text), JSONL audit log
- Actions: write_memory, read_memory, search_memory, list_memories; optional SSE stream for long searches
- License: MIT

See docs/QUICKSTART.md and docs/SPEC.md for details.

## Data Model (Quick Reference)
- A memory is a versioned entry, not a plain KV:
  - id, version, project?, key?, scope (`project|global`), text, tags[], createdAt, ttlSec?, metadata?
- Keyed writes (project + key) auto‑increment version; `read_memory` returns the latest for that key.
- Unkeyed writes (no key) are append‑only notes; use `search_memory`/`list_memories` to retrieve.

## API Docs (Swagger)
- Start server: `python3 -m server.app --home ~/.roadnerd/memorydb --port 7090`
- Open: `http://127.0.0.1:7090/docs` (Swagger) and `/redoc` (ReDoc)
- Bodies are fully typed (project, scope, key, text, tags, ttlSec, metadata); responses include `createdAt`.

## MCP (Streamable HTTP)
- Endpoint: `POST http://127.0.0.1:7090/mcp` (JSON‑RPC 2.0)
- Supported methods: `initialize`, `tools/list`, `tools/call` (tools: `write_memory`, `read_memory`, `search_memory`, `list_memories`).
- Gemini CLI (user config `~/.gemini/settings.json`):
  ```json
  {
    "mcpServers": {
      "memory-mcp": {
        "httpUrl": "http://127.0.0.1:7090/mcp",
        "timeout": 15000,
        "headers": { "Authorization": "Bearer ${MEM_TOKEN}" }
      }
    }
  }
  ```
  Then run `gemini mcp list` and use the tools in chat.

## Examples
- Write (keyed):
  ```bash
  curl -s -X POST http://127.0.0.1:7090/actions/write_memory \
    -H 'Content-Type: application/json' \
    -d '{"project":"RoadNerd","scope":"project","key":"policy","text":"Dynamic tokens: max(512, n*120)","tags":["decision","prompt"],"metadata":{"source":"doc"}}'
  ```
- Read latest by key:
  ```bash
  curl -s -X POST http://127.0.0.1:7090/actions/read_memory \
    -H 'Content-Type: application/json' \
    -d '{"project":"RoadNerd","key":"policy"}'
  ```
- Search:
  ```bash
  curl -s -X POST http://127.0.0.1:7090/actions/search_memory \
    -H 'Content-Type: application/json' \
    -d '{"query":"tokens","project":"RoadNerd","k":5}'
  ```
