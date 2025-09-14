Playwright UI Smoke — Test‑Start‑MCP

Intent
- A minimal UI (`/mcp_ui`) to exercise `initialize`, `tools/list`, and `run_script` against the server.

This mirrors other MCPs:
- Install Playwright: `npm i -D playwright && npx playwright install --with-deps chromium`
- Planned run: `node Test-Start-MCP/scripts/ui-playwright.mjs`

Notes
- The server already exposes `/mcp` and a minimal UI at `/mcp_ui` for manual smoke tests.
- A dedicated Playwright script will be added in the next phase to exercise initialize → tools/list → tools/call(run_script).
