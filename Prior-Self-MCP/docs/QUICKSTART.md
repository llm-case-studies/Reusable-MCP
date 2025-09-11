# Prior‑Self MCP Quickstart

## 1) Create a workspace
```
export PRIOR_SELF_HOME="$HOME/.roadnerd/chatdb"
mkdir -p "$PRIOR_SELF_HOME/transcripts"
```

## 2) Append sample rows (ingest)
```
python3 ingest/append.py --chat-id session_1 --project RoadNerd \
  --role assistant --text "Dynamic tokens for brainstorm set to max(512, n*120)"
```

## 3) Build index
```
python3 indexer/build_index.py --home "$PRIOR_SELF_HOME"
```

## 4) Run server
```
python3 server/app.py --home "$PRIOR_SELF_HOME" --host 127.0.0.1 --port 7070
```

## 5) Call actions
```
curl -s http://127.0.0.1:7070/healthz
curl -s -X POST http://127.0.0.1:7070/actions/search_previous_chats \
  -H 'Content-Type: application/json' \
  -d '{"query":"brainstorm tokens", "project":"RoadNerd"}' | jq .
```

## Serena/Context7
- Register this server as an HTTP MCP tool.
- Actions: search_previous_chats, get_chat_context, summarize_decisions, list_sessions.
