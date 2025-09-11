# Prior‑Self MCP — SPEC (Draft)

## JSONL Schema (one object per line)
- chat_id: string (e.g., session_2025-09-10_roadnerd)
- project: string (e.g., RoadNerd)
- ts: ISO timestamp
- role: "user" | "assistant" | "tool"
- text: string (redacted on ingest if enabled)
- tags: [string]
- tool_name?: string
- tool_input?: object|string
- tool_output_path?: string (large outputs saved to disk)
- decisions?: object (key→value)
- files_touched?: [string]
- env?: object (e.g., RN_* settings)

## SQLite Schema
- messages(id, chat_id, project, ts, role, text, tags)
- decisions(id, chat_id, ts, key, value, file_path)
- fts_messages(text) (FTS5 virtual table)

## MCP Actions (HTTP)
- search_previous_chats { query, project?, from?, to?, k? } → { items: [{chat_id, ts, score, text_excerpt}] }
- get_chat_context { chat_id, before?: int, after?: int, max_tokens?: int } → { messages: [...] }
- summarize_decisions { chat_id, file_path?, date_range? } → { decisions: [...] }
- list_sessions { project?, date_range? } → { sessions: [{chat_id, first_ts, last_ts, message_count}] }
- find_similar_problems { issue_text, project?, k? } → { matches: [...] } (optional, embeddings)

## HTTP Endpoints
- GET /healthz → 200 {ok:true}
- POST /actions/search_previous_chats
- POST /actions/get_chat_context
- POST /actions/summarize_decisions
- POST /actions/list_sessions
- POST /actions/find_similar_problems (optional)

## Auth & Limits
- Optional bearer token via PRIOR_SELF_TOKEN for protected deployments
- Max response sizes; large contexts returned as paths to files
