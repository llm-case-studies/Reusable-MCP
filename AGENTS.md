# Repository Guidelines

## Project Structure & Module Organization
- This is a small Python monorepo of reusable MCP servers:
  - `Code-Log-Search-MCP/` — code/log search service (`server/`, `tests/`, `docs/`, `deploy/`, `openapi.yaml`).
  - `Memory-MCP/` — durable memory service (`server/`, `tests/`, `docs/`, `deploy/`).
  - `Prior-Self-MCP/` — prior chat context service (`server/`, `indexer/`, `ingest/`, `tests/`, `docs/`).
- Runtime code for each service lives under its `server/` package. Tests are under `*/tests` (pytest).

## Build, Test, and Development Commands
- Setup once (per service): `python3 -m venv .venv && source .venv/bin/activate && pip install fastapi uvicorn pytest`
- Run tests:
  - `pytest -q Code-Log-Search-MCP/tests`
  - `pytest -q Memory-MCP/tests`
  - `pytest -q Prior-Self-MCP/tests`
- Run locally:
  - Code-Log-Search: `./Code-Log-Search-MCP/run-tests-and-server.sh` or `python3 Code-Log-Search-MCP/server/app.py --default-code-root <path> --logs-root <path>` (env: `CLS_CODE_ROOT`, `RN_LOG_DIR`, `CLS_TOKEN`).
  - Memory-MCP: `./Memory-MCP/run-tests-and-server.sh` or `python3 Memory-MCP/server/app.py --home <dir>` (env: `MEM_HOME`, `MEM_TOKEN`).
  - Prior-Self-MCP: `python3 Prior-Self-MCP/indexer/build_index.py --home ~/.roadnerd/chatdb` then `python3 Prior-Self-MCP/server/app.py`.

## Coding Style & Naming Conventions
- Python 3.10+; follow PEP 8/257. Use 4‑space indentation, type hints, and module/function `snake_case`; class `CapWords`.
- Keep modules focused (HTTP in `server/app.py`, logic helpers in sibling modules). Tests named `test_*.py` mirroring modules.

## Testing Guidelines
- Framework: `pytest`. Prefer `tmp_path` and in‑process FastAPI `TestClient` (see existing tests).
- Aim for fast, hermetic tests (no network). Include edge cases and minimal fixtures.
- Run `pytest -q <service>/tests` before opening a PR.

## Commit & Pull Request Guidelines
- Commits: imperative mood, concise subject (≤72 chars). Scope prefix encouraged (e.g., `memory: add list endpoint`). Reference issues in body.
- PRs: include summary, rationale, test plan (commands), and any screenshots of `/search` or `/mem` pages if UI changes impact behavior.

## Security & Configuration Tips
- Do not commit secrets or local DBs. Use env tokens for auth (`CLS_TOKEN`, `MEM_TOKEN`). Default ports: 7080 (CLS), 7090 (MEM), 7070 (Prior‑Self). Data roots default to `~/.roadnerd/...`.
