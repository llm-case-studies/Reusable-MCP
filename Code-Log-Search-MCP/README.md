# Code‑Log‑Search‑MCP

Lightweight HTTP/SSE MCP server for fast, cheap search over code and logs.

- Transport: HTTP + SSE (no stdio)
- Actions: search_code, search_logs; SSE stream for large code searches
- Backend: ripgrep for speed; optional SQLite FTS for logs in future phases
- License: MIT

See docs/QUICKSTART.md for setup and usage.
