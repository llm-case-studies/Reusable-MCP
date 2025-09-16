# Test‑Start‑MCP — End‑to‑End Tutorial (UI + Admin + Preflight)

This walkthrough shows how to validate Test‑Start‑MCP end‑to‑end using the built‑in UIs and the new Admin + Pre‑flight features.

## Prerequisites
- Python venv with FastAPI + Jinja2:
  - `python3 -m venv .venv && . .venv/bin/activate && pip install -U pip fastapi uvicorn jinja2 pytest`
- Start the server:
  - `./Test-Start-MCP/run-tests-and-server.sh`
- Recommended env:
  - `TSM_ALLOWED_ROOT` points to this repo path
  - `TSM_LOG_DIR=Test-Start-MCP/logs`
  - Optional app auth: `TSM_TOKEN`
  - Admin: `TSM_ADMIN_TOKEN` (required for `/admin`)

## UI Walkthrough — MCP Playground
- Open: `http://127.0.0.1:7060/mcp_ui`
- Initialize
  - Click “initialize” → should display `{ protocolVersion: "2025-06-18" }`.
- List Tools
  - Click “tools/list” → shows tools: `run_script`, `list_allowed`, `check_script`.
- Call run_script
  - Tool name: `run_script`
  - Arguments (JSON):
    ```json
    {
      "path": "<ABS>/Test-Start-MCP/scripts/probe.sh",
      "args": ["--smoke"],
      "timeout_ms": 5000
    }
    ```
  - Click “tools/call” → expect `exitCode: 0`, short stdout/stderr, and `logPath`.

## UI Walkthrough — Start Page
- Open: `http://127.0.0.1:7060/start`
- Allowed Scripts
  - Click “List Allowed” → shows 4 scripts (runner + probe.py + probe.sh + slow_exit.sh).
- REST Run
  - Path: `<ABS>/Test-Start-MCP/scripts/probe.sh`
  - Args: `--no-tests,--smoke`
  - Click “POST /actions/run_script” → expect `exitCode: 0`.
- SSE Run
  - Path: `<ABS>/Test-Start-MCP/scripts/probe.sh`
  - Args: `--no-tests,--smoke`
  - Click “Open SSE” → expect `stdout`, `stderr`, and `end` events (exitCode 0). Click “Close SSE” to stop.
- Logs Stream
  - Click “Open Logs SSE” → streams today’s JSONL audit lines and a final “End of existing logs”.
- Stats & Health
  - Click “POST /actions/get_stats” → shows totals and recent errors.
  - Click “GET /healthz” → shows health checks and `ok: true`.

## Admin Walkthrough — Rules, Overlays, Audit
- Open: `http://127.0.0.1:7060/admin` (requires admin token).
  - Either append `?admin_token=<TSM_ADMIN_TOKEN>` or set in browser `localStorage.TSM_ADMIN_TOKEN`.
- Refresh State
  - Click “Refresh State” → shows profiles (tester/reviewer/developer/architect) and current rules/overlays.
- Add Rule (Path)
  - Type: `path`
  - Path: `<ABS>/Test-Start-MCP/scripts/probe.sh`
  - Flags Allowed: `--smoke`
  - TTL Seconds: `60`
  - Click “Add Rule” → expect `{ ok: true, rule: { id, expiresAt } }` and a new row in “Rules”.
- Remove Rule
  - Click “remove” on that row → state refresh shows it gone.
- Assign Profile Overlay
  - Session ID: `sess-ui`
  - Profile: `tester` (or other)
  - TTL Seconds: `120`
  - Click “Assign” → overlays table shows session/profile/expiry.
- Policy Audit
  - Click “Load Today’s Audit” → tail shows `allowlist/add`, `allowlist/remove`, `session/profile` events.

## Pre‑flight (Optional Enforcement)
If you enable preflight enforcement, the server requires a successful preflight per session+path+args before running.

- Enable enforcement and TTL:
  - `export TSM_REQUIRE_PREFLIGHT=1`
  - `export TSM_PREFLIGHT_TTL_SEC=600` # default 600s
- Use a session header for REST/SSE:
  - `X-TSM-Session: sess-123`
- Check script first (REST):
  - `POST /actions/check_script` with `{ path, args }` and header `X-TSM-Session`
  - Response `{ allowed: true }` will record a preflight for that tuple.
- Then run:
  - `POST /actions/run_script` with same `X-TSM-Session, path, args` → should succeed.
- Without preflight, run_script returns `428 E_POLICY` with `preflight_required` or `preflight_expired`.

## Tips — Flags, Sessions, and Caps
- Global flags: `TSM_ALLOWED_ARGS` define the superset.
- Rules can narrow allowed flags (intersection); denied flags remove them entirely.
- Session overlays (profiles) can narrow flags and apply runtime caps.
- Runtime caps enforced during execution:
  - Timeout clamps to the effective `maxTimeoutMs` (overlay/rule min).
  - Output bytes clamp to `maxBytes`.

## Playwright — UI Smokes and MCP Explorer
- Scripted smokes (optional):
  - `node Test-Start-MCP/scripts/ui-playwright.mjs` (MCP UI + Start)
  - `node Test-Start-MCP/scripts/ui-playwright-admin.mjs` (Admin flows)
- MCP‑driven exploratory testing:
  - Use the Playwright MCP server to drive `/mcp_ui`, `/start`, and `/admin` with screenshots.
  - Avoid browser lock errors by starting Playwright MCP with `--isolated`:
    - `npx @playwright/mcp@latest --isolated`
  - If you see a `SingletonLock` error, kill the owning PID or remove the lock file, then relaunch with `--isolated`.

## Troubleshooting
- 401 Unauthorized on Admin
  - Provide `Authorization: Bearer <TSM_ADMIN_TOKEN>`, `?admin_token=…`, or set `localStorage.TSM_ADMIN_TOKEN`.
- 428 E_POLICY (preflight_required)
  - Enable preflight TTL and run `check_script` first; include `X-TSM-Session`.
- Browser lock errors with Playwright
  - Use `--isolated` for the Playwright MCP; ensure no lingering Chromium processes hold the lock.

---
See also:
- `docs/ADMIN-PREFLIGHT-SPEC.md` (full spec)
- `docs/QUICKSTART.md` (endpoints and config)
- `docs/PLAYWRIGHT-SMOKE.md` (UI smokes and admin smoke)

