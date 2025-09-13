# Code‑Log‑Search‑MCP

Lightweight HTTP/SSE MCP server for fast, cheap search over code and logs.

- Transport: HTTP + SSE (no stdio)
- Actions: search_code, search_logs; SSE stream for large code searches
- Backend: ripgrep for speed; optional SQLite FTS for logs in future phases
- License: MIT

See docs/QUICKSTART.md and docs/MCP-QUICKSTART.md for setup and MCP usage.

UI smoke (Playwright)
- See docs/PLAYWRIGHT-SMOKE.md for a minimal Playwright-based UI smoke that drives `/mcp_ui` and verifies calls.

## Security
- Defaults to 127.0.0.1. Add a bearer token (CLS_TOKEN) if exposing beyond localhost.
- Result sizes capped by `maxResults`; prefer streaming for large queries.

## Logging & Observability
- Control via env:
  - `CLS_LOG_LEVEL=INFO|DEBUG|...`
  - `CLS_LOG_DIR=<dir>` or `CLS_LOG_FILE=<file>` (with optional `CLS_LOG_TS=1`)
  - Rotation: `CLS_LOG_ROTATE=<bytes>`, `CLS_LOG_BACKUPS=<n>`
- Logs include basic events for code/logs searches and MCP tool calls.
