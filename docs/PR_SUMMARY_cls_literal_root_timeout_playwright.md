Title: cls: literal search, rg "--" safety, root allowlist + timeout; runner help; Playwright UI smoke; tests

Summary
- Harden Code‑Log‑Search search tooling and improve dev ergonomics:
  - Add fixed‑string matching via `literal: true` (maps to `rg -F`).
  - Prevent ripgrep option injection by inserting `--` before query.
  - Enforce `root` allowlist: requested root must resolve under `default_code_root` (returns `forbidden_root` otherwise).
  - Add `timeoutMs` to bound `rg` runtime; SSE reuses durationSec as a time budget.
  - Improve dev runner: defaults + `.env` support, helpful `--help`, smoke runs MCP init/list and code/logs searches.
  - Add Playwright UI smoke that drives `/mcp_ui` (initialize → tools/list → literal call → forbidden_root probe).
- Prior‑Self quality‑of‑life: add a dev runner (tests + seed + smoke + serve) matching the Memory/CLS pattern.

Rationale
- Security & robustness:
  - Using `--` stops user queries from being parsed as ripgrep options (e.g., `--pre`).
  - Root allowlist prevents traversal outside the configured project root.
  - `literal` improves small‑model reliability; `timeoutMs` mitigates pathological regex/long scans.
- DX & consistency: all MCPs share a common runner pattern and test pages; UI smoke provides fast verification.

Changes (high‑level)
- Code‑Log‑Search‑MCP
  - server/search.py: add `--`, `literal` flag, optional `timeout_ms`, non‑blocking read with kill on timeout.
  - server/app.py: sanitize root against `default_code_root`, plumb `literal` and `timeoutMs` through REST/MCP/SSE, log DEBUG details.
  - tests/test_mcp.py: add literal + forbidden_root tests (MCP + REST).
  - tests/test_search.py: add literal=True case.
  - docs: SPEC (new params), MCP-QUICKSTART (literal example), PLAYWRIGHT-SMOKE.md, Gemini-Flash-Test-Prompt.md.
  - scripts/ui-playwright.mjs: minimal Playwright smoke for `/mcp_ui`.
  - run-tests-and-server.sh: config block, `.env` support, `--help`, dependency checks, improved smoke.
- Prior‑Self‑MCP
  - run-tests-and-server.sh: new runner with `.env`, seed + index + smoke (initialize/list/search_previous_chats).
- Repo hygiene
  - .gitignore: ignore `.gemini/`, `.tmp_memdb/`, service logs.

Test Plan
- Unit tests
  - `pytest -q Code-Log-Search-MCP/tests` → expected: 2 passed, 3 skipped (skips are FastAPI-dependent; run with fastapi/uvicorn installed to enable).
- Dev runners
  - CLS: `./Code-Log-Search-MCP/run-tests-and-server.sh` (or `--help`).
  - Prior‑Self: `./Prior-Self-MCP/run-tests-and-server.sh` (seeds transcripts and verifies MCP).
- Playwright UI smoke (optional)
  - `cd Code-Log-Search-MCP && npm i -D playwright && npx playwright install --with-deps chromium`
  - `node Code-Log-Search-MCP/scripts/ui-playwright.mjs`
- Manual curls (CLS)
  - Forbidden root: `curl -s -X POST :7080/actions/search_code -H 'Content-Type: application/json' -d '{"query":"x","root":"/"}'` → 400 `{error:"forbidden_root"}`.
  - Literal: MCP tools/call with `{ "name":"search_code", "arguments": { "query":"README MCP", "root":"<repo>", "literal": true } }` returns hits.

Security Notes
- Prevents ripgrep option injection with `--`.
- Denies roots outside `default_code_root`.
- Adds `timeoutMs` to reduce risk of DoS via complex patterns/large scans.

Screenshots (optional)
- See docs/PLAYWRIGHT-SMOKE.md for steps; MCP UI shows initialize/list and returns hits for literal calls.

