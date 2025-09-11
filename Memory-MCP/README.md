# Memory‑MCP

A small, reusable HTTP/SSE MCP service that provides durable, project‑scoped memory for agents.

- Transport: HTTP + SSE (no stdio)
- Storage: SQLite + FTS (text), JSONL audit log
- Actions: write_memory, read_memory, search_memory, list_memories; optional SSE stream for long searches
- License: MIT

See docs/QUICKSTART.md and docs/SPEC.md for details.
