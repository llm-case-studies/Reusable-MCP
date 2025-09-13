Code‑Log‑Search‑MCP — MCP Quickstart

Overview
- HTTP actions: `/actions/search_code`, `/actions/search_logs`
- SSE: `/sse/search_code_stream`
- MCP: Streamable HTTP JSON‑RPC on `POST /mcp` with `initialize`, `tools/list`, `tools/call`.

Prerequisites
- Python 3.10+
- ripgrep installed at `/usr/bin/rg` (or install `ripgrep` via your package manager; this service invokes `/usr/bin/rg`).

Run (local)
```
python3 Code-Log-Search-MCP/server/app.py --host 127.0.0.1 --port 7080 \
  --default-code-root "$PWD" \
  --logs-root "$HOME/.roadnerd/logs"
```

MCP JSON‑RPC (curl)
1) Initialize
```
curl -sS -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}' \
  http://127.0.0.1:7080/mcp | jq .
```
2) Tools list
```
curl -sS -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  http://127.0.0.1:7080/mcp | jq .
```
3) Call search_code
```
curl -sS -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_code","arguments":{"query":"TODO","root":"'"$PWD"'","maxResults":10,"literal":false}}}' \
  http://127.0.0.1:7080/mcp | jq .
```
4) Call search_logs
```
curl -sS -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"search_logs","arguments":{"query":"brainstorm","date":"20250101","mode":"brainstorm","maxResults":10}}}' \
  http://127.0.0.1:7080/mcp | jq .
```

Gemini CLI integration
Add to `~/.gemini/settings.json` or project `.gemini/settings.json`:
```
{
  "mcpServers": {
    "code-log-search": {
      "httpUrl": "http://127.0.0.1:7080/mcp",
      "timeout": 15000
    }
  }
}
```
Then run `gemini mcp list`, and use tools `search_code` and `search_logs` in chat.

Testing guidance (from Memory‑MCP Gemini tests)
- Multi‑keyword and special characters: prefer exact tokens for `search_code`; ripgrep treats patterns as regex by default. Quote or escape special chars if needed.
- Use `literal: true` to switch to fixed-string matching (rg -F) for small-model friendly behavior.
- Validate globs and context lines:
  - Use `globs: ["*.py","*.md"]` to narrow scope
  - Set `contextLines: 1..3` to provide minimal context for small models
- Logs filtering: include `date` and `mode` to get deterministic results in evaluations.

Troubleshooting
- `ripgrep (rg) not found` → install `ripgrep` (ensure at `/usr/bin/rg`).
- No results → confirm `root` path and `globs`; try a simpler literal pattern.
- Large outputs → increase `maxResults` or use SSE at `/sse/search_code_stream`.
Browser test pages
- Swagger: http://127.0.0.1:7080/docs and /redoc
- MCP UI: http://127.0.0.1:7080/mcp_ui (initialize, tools/list, tools/call)
- Search UI: http://127.0.0.1:7080/search (REST helper)
