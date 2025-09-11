# Prior‑Self MCP Whitepaper (Draft)

## Motivation
Agent handoffs lose valuable context. Terminal sessions are short‑lived; web chats are siloed. Teams re‑discover technical decisions and repeat experiments. We need a lightweight, project‑scoped memory that any agent can query safely.

## Vision
A small MCP server that indexes previous chats and tool runs as structured JSONL and exposes search/context/summarize actions. Agents call it when stuck, to retrieve prior decisions, similar problems, and “context packs” for quick continuation.

## Design Principles
- Minimal friction: append JSONL rows during work; index later
- Portable: SQLite + FTS; optional embeddings when available
- Safe: per‑project scoping; redaction on ingest; HTTP transport
- Composable: generic actions usable from Serena/context7 or any Agentic SDK

## Architecture
- Ingest: CLI appends JSONL rows (role, text, tool inputs/outputs, tags)
- Indexer: builds SQLite with FTS and (optionally) embeddings
- Server: FastAPI HTTP endpoints implementing MCP‑style actions

## Benefits
- Continuity across assistant transitions (GPT → Claude → …)
- Faster resolution via pattern recall and decision summaries
- Auditable, structured memory that improves with use

## Future Work
- Automatic decision extraction from diffs and test runs
- Project dashboards (recent changes, recurring issues)
- Live “context pack” assembly directly into agent prompts
