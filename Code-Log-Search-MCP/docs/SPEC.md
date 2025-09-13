# Code‑Log‑Search‑MCP — SPEC (Draft)

## Actions
- POST /actions/search_code
  - Request: { query: string, root?: string, globs?: string[], maxResults?: number, contextLines?: number, literal?: boolean, timeoutMs?: number }
  - Response: { hits: [{ file: string, line: number, preview: string }] }
  - Notes: `root` must resolve under `default_code_root`; server rejects requests with an external root (`forbidden_root`).
- GET /sse/search_code_stream?query=…&root=…&maxResults=…
  - Streams text/event-stream; events: {event:"message", data: hit}, terminates with {event:"end", data:{count}}
- POST /actions/search_logs
  - Request: { query: string, date?: YYYYMMDD, mode?: string, maxResults?: number }
  - Response: { entries: object[] }
- GET /healthz → { ok: true, code_root, logs_root }

## Limits & Behavior
- Results capped by maxResults; previews truncated to line length
- SSE emits one JSON hit per event; include a final summary
- Large outputs must be saved to paths (future); responses should remain compact

## Auth (Optional)
- Bearer token via CLS_TOKEN (future); reject unauthorized requests

## Errors
- 400 on invalid params; 500 with {error} on server faults
