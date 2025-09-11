# Memory‑MCP — SPEC (Draft)

## Actions (HTTP)
- write_memory (POST /actions/write_memory)
  - Request: { project?: string, scope?: 'project'|'global', key?: string, text: string, tags?: string[], ttlSec?: number, metadata?: object }
  - Response: { id: string, version: number, createdAt: string }
- read_memory (POST /actions/read_memory)
  - Request: { id?: string, project?: string, key?: string }
  - Response: { entry?: { id, version, project, key, scope, text, tags, createdAt, ttlSec?, metadata? } }
- search_memory (POST /actions/search_memory)
  - Request: { query: string, project?: string, tags?: string[], k?: number, from?: string, to?: string }
  - Response: { items: [{ id, project, key, text, tags, createdAt }] }
- list_memories (POST /actions/list_memories)
  - Request: { project?: string, tags?: string[], limit?: number, offset?: number }
  - Response: { items: [{ id, project, key, text, tags, createdAt }] }
- stream_search_memory (GET /sse/stream_search_memory?query=…&project=…&k=…)
  - SSE stream of JSON hits; ends with summary
- healthz (GET /healthz) → { ok: true, home }

## Storage
- SQLite: tables `memories(id TEXT PRIMARY KEY, version INTEGER, project TEXT, key TEXT, scope TEXT, text TEXT, tags TEXT, created_at TEXT, ttl_sec INTEGER, metadata TEXT)`
- FTS: `fts_memories(text)` referencing rowid from `memories`
- JSONL audit log: append‑only record of writes

## Auth
- Optional bearer token via ENV `MEM_TOKEN` for all actions/SSE

## Errors
- 400 for invalid params; 401 unauthorized; 500 for server errors
