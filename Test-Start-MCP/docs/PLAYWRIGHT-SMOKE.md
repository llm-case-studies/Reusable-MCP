Playwright UI Smoke — Test‑Start‑MCP

Intent
- A minimal UI (`/mcp_ui`) to exercise `initialize`, `tools/list`, and `run_script` against the server.

This mirrors other MCPs:
- Install Playwright: `npm i -D playwright && npx playwright install --with-deps chromium`
- Run: `node Test-Start-MCP/scripts/ui-playwright.mjs`

Options
- `TSM_URL=http://127.0.0.1:7060` to point to the server (default is 127.0.0.1:7060).
- `TSM_TOKEN=…` to set bearer auth; script stores it in localStorage for `/mcp_ui`.
- `TSM_PLAYWRIGHT_SCRIPT=…` absolute path to an allow‑listed script (default uses Memory-MCP runner in this repo).
- `HEADFUL=1` to show the browser.

What it checks
- `/mcp_ui` initialize and tools/list flows.
- `tools/call(run_script)` using a safe allow‑listed script with `--no-tests --smoke`.
- `/start` UI flows:
  - List allowed scripts
  - Run Script (REST) and inspect result
  - Run Script (SSE) and receive stdout/stderr/end
  - Open Logs Stream and receive events
  - Get Stats and Health

Notes
- Server logs are written to `Test-Start-MCP/logs/` (see SPEC for details).
