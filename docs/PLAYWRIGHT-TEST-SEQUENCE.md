Playwright Test Sequence — Start Servers → Verify UIs → Run UI Smokes

Purpose
- Provide a repeatable, lightweight flow to start each MCP server, verify its test UIs are reachable, and run a minimal Playwright UI smoke.

Prerequisites
- Python 3.10+ with a shared repo venv activated (`.venv`) and deps installed: `pip install -U fastapi uvicorn pytest`
- ripgrep installed (`/usr/bin/rg`) for Code‑Log‑Search (e.g., `sudo apt install ripgrep`)
- Node.js 18+ and npm for Playwright

Code‑Log‑Search‑MCP
1) Start the server (runner has defaults + `.env` support)
```
./Code-Log-Search-MCP/run-tests-and-server.sh
# --help shows flags and config
```

2) Verify test UIs are available
- Swagger: http://127.0.0.1:7080/docs (should return 200 and list endpoints)
- MCP UI: http://127.0.0.1:7080/mcp_ui (should render initialize / tools/list / tools/call)
- REST helper UI: http://127.0.0.1:7080/search (optional)

3) Run the Playwright UI smoke
```
cd Code-Log-Search-MCP
npm init -y
npm i -D playwright
npx playwright install --with-deps chromium
node Code-Log-Search-MCP/scripts/ui-playwright.mjs
```
What it checks
- Initialize and list tools via `/mcp_ui`
- Calls `search_code` with `{ literal: true }` and asserts a structured response
- Attempts a forbidden root call (`root: "/"`) and logs whether the UI shows the error (API enforcement is covered by unit tests)

Prior‑Self‑MCP
1) Start the server (runner seeds+indexes+smokes, then serves)
```
./Prior-Self-MCP/run-tests-and-server.sh
```

2) Verify test UIs are available
- Swagger: http://127.0.0.1:7070/docs
- MCP UI: http://127.0.0.1:7070/mcp_ui

3) Run the Playwright UI smoke
```
cd Prior-Self-MCP
npm init -y
npm i -D playwright
npx playwright install --with-deps chromium
node Prior-Self-MCP/scripts/ui-playwright.mjs
```
What it checks
- Initialize and list tools via `/mcp_ui`
- Calls `search_previous_chats` on seeded data and `get_chat_context`

Memory‑MCP (manual UI check)
- Swagger: http://127.0.0.1:7090/docs
- MCP UI: http://127.0.0.1:7090/mcp_ui
- REST UI: http://127.0.0.1:7090/mem
- A Playwright smoke can be added similarly if desired, but is not required.

Troubleshooting
- 404 on `/mcp_ui` or `/docs`: ensure the server process is running (runner serves in foreground). Check logs under `<service>/logs` or terminal output.
- 401 Unauthorized: set the relevant token in the browser (e.g., `localStorage.setItem('CLS_TOKEN','secret')`) or export env tokens before starting servers.
- ripgrep not found: install `ripgrep` so `/usr/bin/rg` exists.
- Prior‑Self error `no such column: fts_messages`: rebuild the index (runner does this automatically on `--smoke`), or run `python3 Prior-Self-MCP/indexer/build_index.py --home "$HOME/.roadnerd/chatdb"`.
- Forbidden root error (CLS): expected when `root` is outside `default_code_root`. Use an allowed root or adjust defaults.

References
- Code‑Log‑Search Playwright smoke: `Code-Log-Search-MCP/docs/PLAYWRIGHT-SMOKE.md`
- Prior‑Self Playwright smoke: `Prior-Self-MCP/docs/PLAYWRIGHT-SMOKE.md`
- Dev pattern and runners: `docs/MCP-DEV-PATTERN.md`

