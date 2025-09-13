Playwright UI Smoke — Code‑Log‑Search MCP

Prereqs
- Node.js 18+
- Playwright installed locally

Install Playwright (one-time)
```
cd Code-Log-Search-MCP
npm init -y
npm i -D playwright
npx playwright install --with-deps chromium
```

Run the UI smoke
```
node Code-Log-Search-MCP/scripts/ui-playwright.mjs
```

What it does
- Opens `/mcp_ui`
- initialize → tools/list
- Calls `search_code` with `{ literal: true, root: <repo> }` and asserts a structured response
- Attempts a forbidden root call (root: "/"); if the UI surfaces the error, logs it; API enforcement is covered by unit tests

Env overrides
- `CLS_BASE` (default `http://127.0.0.1:7080`)
- `CLS_CODE_ROOT` (default `process.cwd()`, recommend repo root)

