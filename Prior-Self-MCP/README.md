# Prior‑Self MCP (Previous Chat Context Server)

A small, reusable MCP tool server that gives agents access to prior chat context across sessions and projects. It stores transcripts in JSONL, indexes them (SQLite FTS), and exposes simple actions: search_previous_chats, get_chat_context, summarize_decisions, list_sessions.

- Language: Python 3.10+
- Transport: HTTP (stable for larger payloads)
- License: MIT

## Features
- JSONL ingest CLI (append fast; no DB required to log)
- SQLite + FTS indexer (builds searchable DB from JSONL)
- FastAPI server exposing MCP‑style actions over HTTP
- Optional embeddings backend (MiniLM) when installed; heuristic fallback otherwise

## Layout
- server/app.py — HTTP API (health, actions)
- ingest/append.py — append transcript rows to JSONL
- indexer/build_index.py — build SQLite FTS index from JSONL
- docs/ — WHITEPAPER, SPEC, QUICKSTART

See docs/QUICKSTART.md to ingest, index, and run the server.

MCP
- Streamable HTTP endpoint at `POST /mcp` with tools: search_previous_chats, get_chat_context, list_sessions, summarize_decisions.
- See docs/MCP-QUICKSTART.md for curl examples.

Dev runner
- `./run-tests-and-server.sh` — runs tests, seeds transcripts, builds index, smoke tests MCP, then serves (edit defaults or use `.env`).

UI smoke (Playwright)
- See docs/PLAYWRIGHT-SMOKE.md for a minimal UI smoke that drives `/mcp_ui` and verifies calls.

Test UIs
- `/docs` (Swagger), `/mcp_ui` (MCP playground), `/start` (interactive UI)

## Auth
- Optional bearer token via `PRIOR_TOKEN` (or `PRIOR_SELF_TOKEN`). If set, all endpoints (including `/mcp`) require `Authorization: Bearer <token>`.

## Logging
- Control via env:
  - `PRIOR_LOG_LEVEL=INFO|DEBUG|...`
  - `PRIOR_LOG_DIR=<dir>` or `PRIOR_LOG_FILE=<file>` (with optional `PRIOR_LOG_TS=1`)
  - Rotation: `PRIOR_LOG_ROTATE=<bytes>`, `PRIOR_LOG_BACKUPS=<n>`

## Dev test pages
- Swagger: `http://127.0.0.1:7070/docs` (and `/redoc`) for REST actions
- MCP UI: `http://127.0.0.1:7070/mcp_ui` (initialize, tools/list, tools/call)
