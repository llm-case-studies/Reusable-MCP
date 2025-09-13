Playwright UI Smoke — Prior‑Self MCP

Prereqs
- Node.js 18+
- Playwright installed locally

Install Playwright (one-time)
```
cd Prior-Self-MCP
npm init -y
npm i -D playwright
npx playwright install --with-deps chromium
```

Seed sample transcript and start the server (if not using the runner)
```
export PRIOR_SELF_HOME="$HOME/.roadnerd/chatdb"
mkdir -p "$PRIOR_SELF_HOME/transcripts"
python3 ingest/append.py --chat-id s1 --project Smoke --role assistant --text "tokens brainstorm"
python3 indexer/build_index.py --home "$PRIOR_SELF_HOME"
python3 server/app.py --home "$PRIOR_SELF_HOME" --host 127.0.0.1 --port 7070
```

Run the UI smoke
```
node Prior-Self-MCP/scripts/ui-playwright.mjs
```

What it does
- Opens `/mcp_ui`
- initialize → tools/list
- Calls `search_previous_chats` with `{ query: "tokens", project: "Smoke", k: 5 }`
- Calls `get_chat_context` with `{ chat_id: "s1" }`

Env overrides
- `PRIOR_BASE` (default `http://127.0.0.1:7070`)

