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
