GPT/Claude/Gemini Collaboration Guide

Goal
- Reduce friction and speed up progress across GPT-family models by aligning on a few conventions: environment, runners, tests, and PR workflow.

Environment & Runners
- One venv per repo at `.venv`; do not create service-specific venvs.
- All service runners prefer the repo venv automatically (no `source` required):
  - `./<Service>/run-tests-and-server.sh` detects and uses `.venv/bin/python`; falls back to `python3`.
  - Tests run via `"$PY_EXE" -m pytest`; if pytest isn’t installed, tests are skipped (server still starts).
- Never `pip install` from inside code; assume `.venv` already has `fastapi uvicorn pytest`.

MCP Service Pattern
- Endpoints: `GET /healthz`, `POST /actions/<tool>`, `POST /mcp` (initialize, tools/list, tools/call), optional `GET /sse/<stream>`.
- Dev UIs: `/docs` (Swagger) and `/mcp_ui` (MCP playground) for every service.
- Security:
  - Optional bearer tokens per service: `MEM_TOKEN`, `CLS_TOKEN`, `PRIOR_TOKEN`, etc.
  - Input validation; allowlists for filesystem/network; timeouts; redaction in logs.
- Logging: `*_LOG_DIR`, `*_LOG_LEVEL`, optional rotation; runner sets sensible defaults for dev logs.

Testing Flow
- Unit tests: `pytest -q <Service>/tests`; prefer FastAPI `TestClient`, `tmp_path`, hermetic inputs.
- UI smoke: Playwright script under `<Service>/scripts/ui-playwright.mjs` (drives `/mcp_ui`).
- MCP testing: Gemini Flash tool calls; results documented in `docs/…Test-Results.md`.

PR Workflow
- Branch naming: `<area>/<brief-topic>` (e.g., `cls/literal-root-timeout-playwright`).
- PR summary: include Summary, Rationale, Changes, Test Plan, and Security Notes; link to any new docs.
- Keep changes surgical; avoid restructuring; prefer additive docs and small, focused diffs.

Scaffolds
- New MCPs follow the same tree:
  - `<Service>/server/app.py` (REST + MCP + optional SSE), `<Service>/run-tests-and-server.sh`
  - `<Service>/docs/SPEC.md`, `QUICKSTART.md`, `PLAYWRIGHT-SMOKE.md`, `PROGRESS_CHECKLIST.md`
  - `<Service>/tests/test_server.py` (start with health + one happy path)
  - `<Service>/deploy/<service>.service`

Do/Don’t
- Do: use repo `.venv`, runners, and standard ports (7090, 7080, 7070, …)
- Do: return strict JSON and JSON‑RPC envelopes; keep responses small
- Don’t: create extra venvs or run shell commands that assume activation state
- Don’t: introduce new CLI/install steps unless discussed; prefer docs over code for scaffolds

