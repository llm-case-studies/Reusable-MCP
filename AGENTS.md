# Repository Guidelines

## Project Structure & Module Organization
- This is a small Python monorepo of reusable MCP servers:
  - `Code-Log-Search-MCP/` — code/log search service (`server/`, `tests/`, `docs/`, `deploy/`, `openapi.yaml`).
  - `Memory-MCP/` — durable memory service (`server/`, `tests/`, `docs/`, `deploy/`).
  - `Prior-Self-MCP/` — prior chat context service (`server/`, `indexer/`, `ingest/`, `tests/`, `docs/`).
- Runtime code for each service lives under its `server/` package. Tests are under `*/tests` (pytest).

## Build, Test, and Development Commands
- One venv per repo (preferred): `python3 -m venv .venv && source .venv/bin/activate && pip install -U pip fastapi uvicorn pytest`
- Runners auto‑use `.venv` (no activation needed): `./<Service>/run-tests-and-server.sh`
- Run tests:
  - `pytest -q Code-Log-Search-MCP/tests`
  - `pytest -q Memory-MCP/tests`
  - `pytest -q Prior-Self-MCP/tests`
- Run locally:
  - Code-Log-Search: `./Code-Log-Search-MCP/run-tests-and-server.sh` (or `python3 Code-Log-Search-MCP/server/app.py --default-code-root <path> --logs-root <path>`)
  - Memory-MCP: `./Memory-MCP/run-tests-and-server.sh` (or `python3 Memory-MCP/server/app.py --home <dir>`)
  - Prior-Self-MCP: `./Prior-Self-MCP/run-tests-and-server.sh`

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
- Do not commit secrets or local DBs. Use env tokens for auth (`CLS_TOKEN`, `MEM_TOKEN`). Default ports:
  - 7010 SysDiag‑MCP (`SYS_HOST`, `SYS_PORT`)
  - 7020 Docker‑MCP (`DOCKER_MCP_HOST`, `DOCKER_MCP_PORT`)
  - 7030 Net‑MCP (`NET_HOST`, `NET_PORT`)
  - 7040 Service‑MCP (`SVC_HOST`, `SVC_PORT`)
  - 7050 Git‑My‑Way‑MCP (`GMW_HOST`, `GMW_PORT`)
  - 7060 Test‑Start‑MCP (`TSM_HOST`, `TSM_PORT`)
  - 7070 Prior‑Self‑MCP
  - 7080 Code‑Log‑Search‑MCP
  - 7090 Memory‑MCP
  - Data roots default to `~/.roadnerd/...`.
  - Dev runners may free their ports before starting to enforce a singleton.

## GPT/Claude/Gemini Notes
- Use repo `.venv` only; runners detect and use it automatically.
- Prefer runners over manual `uvicorn`; they run tests (if installed) and start servers consistently.
- Keep changes small and additive; follow existing endpoint shapes (`/actions/*`, `/mcp`, `/sse/*`) and UI pages (`/docs`, `/mcp_ui`).
- See `docs/GPT-COLLAB-GUIDE.md` for collaboration tips and PR expectations.
