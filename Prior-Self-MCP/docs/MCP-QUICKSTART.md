Prior‑Self‑MCP — MCP Quickstart

Overview
- REST actions: `/actions/search_previous_chats`, `/actions/get_chat_context`, `/actions/list_sessions`, `/actions/summarize_decisions`
- MCP endpoint: `POST /mcp` (Streamable HTTP JSON‑RPC) implementing `initialize`, `tools/list`, `tools/call` for the tools above
- Dev pages: `/docs` (Swagger), `/mcp_ui` (MCP playground), `/start` (interactive testing UI)

Start server
```
python3 Prior-Self-MCP/server/app.py --home "$HOME/.roadnerd/chatdb" --host 127.0.0.1 --port 7070
```

Seed and index (once)
```
export PRIOR_SELF_HOME="$HOME/.roadnerd/chatdb"
mkdir -p "$PRIOR_SELF_HOME/transcripts"
python3 Prior-Self-MCP/ingest/append.py --chat-id s1 --project RoadNerd --role assistant --text "tokens brainstorm"
python3 Prior-Self-MCP/indexer/build_index.py --home "$PRIOR_SELF_HOME"
```

MCP (curl)
```
# initialize
curl -sS -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}' \
  http://127.0.0.1:7070/mcp | jq .

# tools/list
curl -sS -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  http://127.0.0.1:7070/mcp | jq .

# tools/call: search_previous_chats
curl -sS -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_previous_chats","arguments":{"query":"tokens","project":"RoadNerd","k":5}}}' \
  http://127.0.0.1:7070/mcp | jq .

# tools/call: get_chat_context
curl -sS -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_chat_context","arguments":{"chat_id":"s1"}}}' \
  http://127.0.0.1:7070/mcp | jq .
```

Auth
- Optional bearer token via `PRIOR_TOKEN` (or `PRIOR_SELF_TOKEN`). If set, include `Authorization: Bearer <token>` in requests.

Runner
- `./Prior-Self-MCP/run-tests-and-server.sh` — runs pytest, seeds transcripts, builds index, smoke tests MCP, then serves (edit defaults in the script or via `.env`).
