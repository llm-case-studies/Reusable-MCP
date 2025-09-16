# Implementing MCP with Streamable HTTP (and SSE)

This guide shows how to expose a Model Context Protocol (MCP) server over the Streamable HTTP transport (with optional SSE) using Python/FastAPI. It’s written for this monorepo to help you add new MCP servers consistently.

References
- MCP spec: Transports, Lifecycle, Tools
  - https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
  - https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle
  - https://modelcontextprotocol.io/specification/2025-06-18/server/tools

## 1) Transport Overview
- Single endpoint: your server MUST expose one HTTP endpoint path (e.g., `/mcp`) that supports POST (required) and optionally GET for SSE.
- Client → Server (POST): each JSON‑RPC message (or batch) is posted to `/mcp` with `Accept: application/json, text/event-stream`.
  - If body contains only notifications/responses → server returns 202 Accepted, no body.
  - If body contains at least one request → server returns either:
    - `Content-Type: application/json` with a JSON‑RPC response (or batch), or
    - `Content-Type: text/event-stream` SSE where it can stream JSON‑RPC messages (responses, notifications, requests) related to the request.
- Server → Client (GET, optional): client MAY open `GET /mcp` with `Accept: text/event-stream` to receive server‑initiated messages (unrelated to an active request). If not supported, return 405.
- Version header: after initialization, clients SHOULD send `MCP-Protocol-Version: <version>` on subsequent requests.
- Session header (optional): server MAY return `Mcp-Session-Id` in the initialize response; client MUST echo it in subsequent requests.

Security notes
- Validate `Origin` on all requests; bind to `127.0.0.1` for local development; require auth (e.g., `Authorization: Bearer ...`).

Operational logging
- Environment variables (append by default, no truncation):
  - `MEM_LOG_DIR=<dir>`: write logs to `<dir>/app.log` (or `app-YYYYMMDD-HHMMSS.log` when `MEM_LOG_TS=1`).
  - `MEM_LOG_FILE=<file>`: explicit log file path (overrides `MEM_LOG_DIR`).
  - `MEM_LOG_TS=1`: add timestamp to filename when using `MEM_LOG_DIR`.
  - `MEM_LOG_ROTATE=<bytes>` and `MEM_LOG_BACKUPS=<n>`: enable rotating logs.
  - `MEM_LOG_LEVEL=INFO|DEBUG|...`, `MEM_DEBUG=1`: verbose/diagnostics in tool errors.

## 2) Lifecycle Messages
- `initialize` (request) → negotiate protocol version and return server capabilities.
- Client sends `notifications/initialized` after receiving the initialize result.
- During operation, use negotiated capabilities only. For shutdown, close HTTP connections (no specific JSON‑RPC shutdown message).

Minimal initialize shapes
- Request
  ```json
  {"jsonrpc":"2.0","id":1,"method":"initialize","params":{
    "protocolVersion":"2025-06-18",
    "capabilities":{},
    "clientInfo":{"name":"ExampleClient","version":"1.0.0"}
  }}
  ```
- Result
  ```json
  {"jsonrpc":"2.0","id":1,"result":{
    "protocolVersion":"2025-06-18",
    "capabilities":{"tools":{"listChanged": false}},
    "serverInfo":{"name":"MyServer","title":"My Server","version":"0.1.0"},
    "instructions":"Optional human‑readable notes",
    "policy":{ "preflight": { "recommended": true, "enforced": false, "checkTool": "check_script", "sessionHeader": "X-TSM-Session", "ttlSec": 600, "adminLink": "/admin" },
               "allowedRoot": "/abs/root" },
    "session": { "id": "sess-xxxx", "header": "X-TSM-Session" }
  }}
  ```
- Notification (client → server)
  ```json
  {"jsonrpc":"2.0","method":"notifications/initialized"}
  ```

Headers (server → client)
- Include guidance headers on initialize responses so agents can react without reading docs:
  - `X-TSM-Preflight: recommended|required` — hints whether preflight is required (server‑side `TSM_REQUIRE_PREFLIGHT`).
  - `Mcp-Session-Id: sess-xxxx` — optional stable session id; clients MAY echo it using `X-TSM-Session` on subsequent calls.

## 3) Tools: list and call
- Capabilities: servers that expose tools MUST advertise `tools` capability (e.g., `{ "tools": { "listChanged": true|false } }`).
- List tools
  - Request: `{ "jsonrpc":"2.0", "id":2, "method":"tools/list", "params": {"cursor":"optional"} }`
  - Result: `{ "jsonrpc":"2.0", "id":2, "result": { "tools": [ ... ], "nextCursor": null } }`
- Tool definitions
  ```json
  {"name":"write_memory","title":"Write Memory","description":"…",
   "inputSchema": {"type":"object","properties":{…},"required":[…]},
   "outputSchema": {"type":"object","properties":{…}}}
  ```
- Call tools
  - Request: `{ "jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"write_memory","arguments":{…}} }`
  - Result (unstructured + structured):
    ```json
    {"jsonrpc":"2.0","id":3,"result":{
      "content":[{"type":"text","text":"{…serialized…}"}],
      "structuredContent": {…parsed JSON…},
      "isError": false
    }}
    ```
  - Protocol error example: `{ "jsonrpc":"2.0","id":3,"error":{"code":-32602,"message":"Unknown tool: …"} }`
  - Compatibility tip: omit `nextCursor` from `tools/list` when no pagination token is available (some clients expect a string when present).

## 4) FastAPI Implementation Pattern
Create one router with `/mcp` handlers and small helpers to keep code tidy.

- Envelope helpers
  ```py
  def mcp_resp(id_val, result=None, error=None):
      return {"jsonrpc":"2.0","id":id_val, **({"result":result} if error is None else {"error":error})}

  def text_and_structured(obj):
      return {"content":[{"type":"text","text":json.dumps(obj, ensure_ascii=False)}],
              "structuredContent": obj, "isError": False}
  ```
- Tool registry function (static or dynamic)
  ```py
  def mcp_tools():
      return [{"name":"write_memory","title":"Write Memory","description":"…",
               "inputSchema": {"type":"object","properties":{…},"required":["text"]}}, …]
  ```
- POST /mcp handler skeleton
  ```py
  @app.post("/mcp")
  async def mcp_post(request: Request):
      body = await request.json()
      async def handle(msg: dict):
          method = msg.get("method"); mid = msg.get("id"); p = msg.get("params") or {}
          if method == "initialize":
              return mcp_resp(mid, {
                  "protocolVersion": p.get("protocolVersion") or "2025-06-18",
                  "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "MyServer", "title": "My Server", "version": "0.1.0"}
              })
          if method == "notifications/initialized":
              return None  # 202 Accepted for notifications
          if method == "tools/list":
              return mcp_resp(mid, {"tools": mcp_tools(), "nextCursor": None})
          if method == "tools/call":
              name = (p or {}).get("name"); args = (p or {}).get("arguments") or {}
              # dispatch to your internal functions/services, return text_and_structured(data)
              …
          if method == "ping":
              return mcp_resp(mid, {"ok": True})
          return mcp_resp(mid, error={"code": -32601, "message": f"Unknown method: {method}"})

      if isinstance(body, list):
          out = [r for m in body if (r := await handle(m)) is not None]
          return JSONResponse(out) if out else JSONResponse(status_code=202, content=None)
      elif isinstance(body, dict):
          r = await handle(body)
          return JSONResponse(r) if r is not None else JSONResponse(status_code=202, content=None)
      return JSONResponse({"error":"invalid payload"}, status_code=400)
  ```
- GET /mcp (optional SSE)
  - Return 405 if not supported, or open an SSE stream (e.g., `StreamingResponse(generate(), media_type="text/event-stream")`) and emit JSON‑RPC messages as text lines.

Mini MCP test UI
- Provide a small HTML UI at `/mcp_ui` to exercise `initialize`, `tools/list`, and `tools/call` directly against `/mcp`.
- Reuse the same Authorization and payloads clients do; useful to reproduce integration issues quickly.

Standard dev test pages
- FastAPI docs: `/docs` and `/redoc` (auto-exposed by FastAPI) for REST actions (`/actions/*`).
- MCP UI: `/mcp_ui` (HTML playground) for JSON‑RPC flows (initialize, list, call).
- Service-specific sanity pages:
  - Memory‑MCP: `/mem` for writing/searching memories interactively; `/sse/stream_search_memory` for SSE.
  - Code‑Log‑Search‑MCP: `/search` for code/log search UI; `/sse/search_code_stream` for SSE.
  - Prior‑Self‑MCP: lightweight HTTP actions only; use `/mcp_ui` and `/docs`.

## 5) Auth, Origin, and Local‑only
- Enforce bearer token on `/mcp` like our REST endpoints.
- Validate `Origin` to mitigate DNS rebinding.
- For local dev, bind to `127.0.0.1` and prefer user tokens over wide‑open ports.

## 6) Session & Version Headers (optional but recommended)
- On initialize result, include `Mcp-Session-Id` header (generated UUID/JWT). Store server‑side.
- Require `Mcp-Session-Id` for subsequent requests; respond 400/404 if missing/expired.
- After initialize, clients should send `MCP-Protocol-Version: 2025-06-18` on all requests.

## 7) Streaming and Notifications
- If you return SSE in response to a POST request, you MAY stream:
  - JSON‑RPC responses (for each request in the POST), and
  - JSON‑RPC notifications/requests related to the same operation (e.g., progress).
- For standalone server → client notifications unrelated to a request, support `GET /mcp` with SSE.
- For resumability, set `id` on SSE events and honor `Last-Event-ID` (see spec).

## 8) Tool Result Shapes and Errors
- Prefer returning both `content` (human‑readable text) and `structuredContent` (machine‑readable JSON).
- Set `isError: true` in the `result` for tool execution errors (business logic).
- Use JSON‑RPC `error` for protocol errors (unknown methods, bad arguments).

## 9) Gemini CLI Integration
- User or project config file: `~/.gemini/settings.json` or `<project>/.gemini/settings.json`.
- Example entry:
  ```json
  {"mcpServers": {"memory-mcp": {
    "httpUrl": "http://127.0.0.1:7090/mcp",
    "timeout": 15000,
    "headers": {"Authorization": "Bearer ${MEM_TOKEN}"}
  }}}
  ```
- Verify with `gemini mcp list`, then invoke tools in chat. The CLI discovers tools via `tools/list` and calls them with `tools/call`.

Workspaces (for Shell tool)
- If you want Gemini’s Shell tool to run local commands/scripts, add a workspace mapping:
  ```json
  {"workspaces": {"Memory-MCP": "/home/<you>/Projects/Reusable-MCP/Memory-MCP"}}
  ```
- This allows commands like `bash run-tests-and-server.sh` to run within the `Memory-MCP` workspace without absolute paths.

## 10) Testing Checklist (manual)
- Initialize: POST /mcp with `initialize` → get result with capabilities and serverInfo.
- Initialized notification: POST /mcp with `notifications/initialized` → 202.
- Tool discovery: `tools/list` returns your tool definitions.
- Tool calls: each call returns a JSON‑RPC response with `content` and `structuredContent`.
- Error paths: unknown tool → JSON‑RPC `error`; business error → `isError: true`.
- Auth: missing/invalid Authorization → 401. Origin check enforced.

Search safety (FTS)
- Quote user queries for FTS `MATCH` to avoid errors on special tokens, e.g., use `"<query>"`.

## 11) Common Pitfalls
- Returning plain JSON without JSON‑RPC envelope.
- Not honoring 202 for notifications.
- Only supporting JSON output for requests that expect SSE (clients should accept both; servers may choose one).
- Forgetting to advertise capabilities (e.g., `tools`).
- Omitting Accept headers in tests; some clients rely on them when switching between JSON and SSE.

## 12) Example: Where to Look in This Repo
- Minimal working implementation: `Memory-MCP/server/app.py` (`/mcp` handler implements `initialize`, `tools/list`, `tools/call`).
- REST+UI remain available (`/mem`, `/actions/*`) for human testing alongside MCP.

Dev script pattern
- See `Memory-MCP/run-tests-and-server.sh` for a restartable test+server runner with:
  - `--no-tests`, `--clean-home`, `--kill-port`, `--smoke` (healthz + MCP init/list + write/read).
  - Passes `MEM_LOG_DIR` and enables timestamped logs for easier analysis.

With this pattern you can add MCP to new services by: defining tool schemas, writing a dispatcher in `/mcp`, and bridging to your existing Python functions. Keep security (Origin, auth) on by default.
