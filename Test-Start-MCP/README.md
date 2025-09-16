# Test‑Start‑MCP

Safely start and smoke‑test local MCP services from models when their sandboxes can’t run scripts. This service runs only allow‑listed scripts with validated flags, streams output, and writes audit logs.

- Spec: see `docs/SPEC.md`
- Quickstart: see `docs/QUICKSTART.md`
- UI: `/mcp_ui` (minimal MCP playground)
- Runner: `./Test-Start-MCP/run-tests-and-server.sh`

Status: Implemented. Endpoints: `/actions/run_script`, `/actions/list_allowed`, `/sse/run_script_stream`, `/mcp`, `/healthz`.

Test UIs
- `/docs` (Swagger), `/mcp_ui` (MCP playground), `/start` (interactive UI)
- UI assets are served from `/static` and templates under `server/templates` for easier debugging and maintenance.

Ports
- Default host/port: `127.0.0.1:7060` (set via `TSM_HOST`, `TSM_PORT`).
- The runner enforces a singleton: it frees the port before starting to avoid stale processes.

Admin & Pre‑flight
- Preflight tool/endpoint: MCP `check_script` and REST `POST /actions/check_script` → returns `allowed`, `reasons`, `matchedRule`, `suggestions`, `adminLink`.
- Admin (token required via `TSM_ADMIN_TOKEN`):
  - `GET /admin` (UI placeholder), `GET /admin/new` (simple Add Rule form)
  - `GET /admin/state` → `{ version, rules, overlays, profiles }`
  - `POST /admin/allowlist/add` (path or scope+patterns), `POST /admin/allowlist/remove`
  - `POST /admin/session/profile` (assign profile overlay to sessionId with TTL)
- Policy file: `TSM_ALLOWED_FILE` (default `Test-Start-MCP/allowlist.json`); a seed with default profiles is included.
- Optional enforcement: `TSM_REQUIRE_PREFLIGHT=1` to require a recent preflight before `run_script`; supply session via `X-TSM-Session` header.
