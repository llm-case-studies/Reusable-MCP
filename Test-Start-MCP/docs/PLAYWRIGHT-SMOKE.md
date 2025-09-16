Playwright UI Smoke — Test‑Start‑MCP

Intent
- A minimal UI (`/mcp_ui`) to exercise `initialize`, `tools/list`, and `run_script` against the server.

This mirrors other MCPs:
- Install Playwright: `npm i -D playwright && npx playwright install --with-deps chromium`
- Run: `node Test-Start-MCP/scripts/ui-playwright.mjs`

Options
- `TSM_URL=http://127.0.0.1:7060` to point to the server (default is 127.0.0.1:7060).
- `TSM_TOKEN=…` to set bearer auth; script stores it in localStorage for `/mcp_ui`.
- `TSM_PLAYWRIGHT_SCRIPT=…` absolute path to an allow‑listed script (default uses this service's `scripts/probe.sh`).
- `HEADFUL=1` to show the browser.
- `TSM_PW_OUT=Test-Start-MCP/.pw-artifacts` to change artifacts output directory (screenshots, console log).

What it checks
- `/mcp_ui` initialize and tools/list flows.
- `tools/call(run_script)` using a safe allow‑listed script with `--no-tests --smoke`.
- `/start` UI flows:
  - List allowed scripts
  - Run Script (REST) and inspect result
  - Run Script (SSE) and receive stdout/stderr/end
  - Open Logs Stream and receive events
  - Get Stats and Health
- Negative checks (best-effort): bad args and forbidden path return 400/403; search_logs returns totals.

Notes
- Server logs are written to `Test-Start-MCP/logs/` (see SPEC for details).

Admin Smoke
- Run: `node Test-Start-MCP/scripts/ui-playwright-admin.mjs`
- Env:
  - `TSM_ADMIN_TOKEN` (required) to authenticate the admin UI
  - `TSM_ADMIN_TARGET` optional absolute path under allowed root (defaults to `Test-Start-MCP/scripts/probe.sh`)
  - `TSM_URL`, `HEADFUL`, `TSM_PW_OUT` same as above
- Checks:
  - Authenticated access to `/admin`
  - Add a path rule with TTL and flags; verify listed in Rules table
  - Remove rule and verify
  - Assign a session profile overlay; load policy audit tail

UI Templates & Static Assets
- HTML templates are rendered via Jinja2 under `server/templates/` (`/start`, `/mcp_ui`, `/admin`).
- CSS/JS are served from `/static` (`server/static/*`) to simplify debugging.
- Make sure to `pip install jinja2` in your venv for templates.
