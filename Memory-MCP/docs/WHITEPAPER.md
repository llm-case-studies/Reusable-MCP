# Memory‑MCP Whitepaper (Draft)

## Motivation
Agents benefit from a durable, shared memory beyond single chat contexts: notes, decisions, parameters, and outcomes that should persist across sessions and be cheaply retrievable without LLM tokens.

## Vision
A machine‑wide, HTTP/SSE memory service with project and global scopes, fast retrieval (FTS, optional embeddings), versioning, and audit logging. Runs offline; optional LAN mode later.

## Design Principles
- Reliable: HTTP + SSE; bounded responses; simple schemas
- Practical: SQLite + FTS for text; JSONL audit for append‑only history
- Safe: localhost bind; optional bearer token (MEM_TOKEN)
- Reusable: independent service; any agent can call its actions

## Architecture
- Storage: SQLite DB with `memories` + FTS table; JSONL audit log
- Server: FastAPI exposing write/read/search/list and stream_search
- Optional embeddings: MiniLM to improve semantic search (phase 2)

## Benefits
- Continuity: retain decisions, parameters, and results across sessions
- Token savings: retrieve small, precise snippets rather than raw files
- Auditability: JSONL log captures memory mutations over time

## Future Work
- Context packs (token‑bounded bundles)
- TTL/retention and export/import
- LAN mode with allowlist subnets
