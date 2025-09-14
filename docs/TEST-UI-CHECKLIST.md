Test UI Checklist (All MCPs)

Use this checklist to validate interactive UIs and Playwright smoke tests for each MCP.

- Pages present
  - `/docs` loads (Swagger UI)
  - `/mcp_ui` works: initialize → tools/list → tools/call
  - `/start` works: domain‑specific flows render and submit

- Auth
  - If token env is set, UIs pick up `*_TOKEN` from localStorage and REST/MCP calls succeed with Authorization header

- REST flows
  - Main actions submit and show results body
  - Error states show structured messages (bad args, forbidden)

- Streaming
  - SSE endpoints stream and UI renders events (e.g., stdout/stderr/end or domain logs/stats)

- Health and stats (when applicable)
  - `/healthz` shows ok:true and any detailed checks
  - Stats endpoints show counters and are updated after actions

- Playwright smoke
  - Script visits `/mcp_ui` and `/start`, runs minimal happy paths, and asserts key fields
  - Env overrides supported: URL, token, domain‑specific target arguments

