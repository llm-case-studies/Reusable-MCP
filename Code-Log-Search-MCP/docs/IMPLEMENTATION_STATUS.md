# Code‑Log‑Search‑MCP — Implementation Status (2025‑09‑11)

## Overview
A small, reusable HTTP/SSE service that provides fast, cheap search over code and logs for agents. It replaces heavyweight, stdio‑based orchestration for the “search” use case and is designed to run as a local, multi‑client singleton.

## Completed (MVP)
- Server (FastAPI) with stable HTTP/SSE transport
  - GET `/healthz`
  - POST `/actions/search_code` → ripgrep backend (JSON), supports `globs`, `maxResults`, `contextLines`
  - GET `/sse/search_code_stream` → streams hits; heartbeats (ping), `durationSec` cap, `maxResults` cap
  - POST `/actions/search_logs` → reads JSONL from `logs_root`, optional `date` (YYYYMMDD) + `mode` filter
- Auth & safety
  - Optional bearer token via `CLS_TOKEN` (all actions + SSE)
  - Bounded results; compact JSON payloads
- Web UI (manual use)
  - GET `/search` — code + log search page; token via localStorage
- OpenAPI
  - `openapi.yaml` covering core endpoints
- Tests & runner
  - Unit tests for code + log search (`tests/test_search.py`)
  - `run-tests-and-server.sh` runs pytest then launches server
- Deploy
  - Example systemd user unit (`deploy/code-log-search-mcp.service`)

## Integration
- Agents call HTTP actions directly; SSE for large code searches
- Works alongside Prior‑Self‑MCP (previous chat context); both are HTTP tools
- RoadNerd can link from `/logs` to this service’s log search

## Proposed Next Steps
- Security & config
  - Add bearer token to OpenAPI securitySchemes; document `CLS_TOKEN`
  - Config file/env docs for `default_code_root`, `logs_root`, bind host/port
- Performance & indexing
  - SQLite FTS for logs (faster complex queries); keep ripgrep for code
  - Optional in‑memory cache for recent queries
- Features
  - Include/exclude globs + ignore file (like `.gitignore` semantics)
  - Multi‑root search configuration
  - Symbol indexing (ctags/tree‑sitter) and cross‑references (phase 3)
- Web UI
  - Result highlighting; copyable links; downloadable JSON
  - Streaming UI polish (progress, cancel)
- Observability
  - Structured access logs; Prometheus metrics (request count/latency)
  - Rate limiting and per‑request hard timeouts
- Packaging
  - pyproject.toml for installable package/entrypoint
  - Dockerfile for quick deployment
- Testing
  - Integration tests using FastAPI TestClient (HTTP + SSE)
  - Larger fixture corpus for logs/code; performance smoke
- MCP tooling
  - Provide an example tool manifest for popular agent runtimes
  - Optional: small CLI client wrapping HTTP/SSE calls

## Usage Pointers
- Start locally: `./run-tests-and-server.sh --host 127.0.0.1 --port 7080 --default-code-root <path> --logs-root $HOME/.roadnerd/logs`
- Web UI: `http://127.0.0.1:7080/search`
- Auth: set `CLS_TOKEN` env var and store the same token in UI localStorage
- SSE: prefer for large searches; use `durationSec`/`maxResults` to bound runs
