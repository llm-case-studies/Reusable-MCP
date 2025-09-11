# Code‑Log‑Search‑MCP Whitepaper (Draft)

## Motivation
Agents need fast, precise search over large codebases and logs without paying token/context costs. General orchestrators that bundle many tools (and stdio) prove unreliable. A small, purpose‑built HTTP/SSE service solves the common need: “find where X occurs, with context,” and “filter logs by query/date/mode.”

## Vision
A system‑wide singleton service that agents call over HTTP/SSE. It streams compact hits, caps payloads, and never blocks on stdio. It’s language‑agnostic and integrates with any agent framework.

## Design Principles
- Lean: ripgrep backend for speed; SQLite FTS optionally for logs
- Reliable: HTTP + SSE; chunked outputs; bounded results
- Multi‑client: single daemon; multiple agents
- Safe: localhost bind; optional bearer token; size/time limits

## Architecture
- Server: FastAPI app exposing /actions/search_code, /actions/search_logs, /sse/search_code_stream
- Backend: ripgrep → JSON parse; logs JSONL reader (mode/date filters)
- Future: SQLite FTS for logs; symbol indexing (ctags/tree‑sitter)

## Benefits
- 80%+ token/context savings vs “agent reads files/raw logs”
- Robustness: no stdio; streaming for long searches
- Reuse: one service across multiple projects and agents

## Future Work
- Web UI for manual searches
- Cross‑refs and symbol browsing
- Full‑text log index and archive/rotation
