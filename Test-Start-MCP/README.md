# Test‑Start‑MCP

Safely start and smoke‑test local MCP services from models when their sandboxes can’t run scripts. This service runs only allow‑listed scripts with validated flags, streams output, and writes audit logs.

- Spec: see `docs/SPEC.md`
- Quickstart: see `docs/QUICKSTART.md`
- UI: `/mcp_ui` (minimal MCP playground)
- Runner: `./Test-Start-MCP/run-tests-and-server.sh`

Status: Implemented. Endpoints: `/actions/run_script`, `/actions/list_allowed`, `/sse/run_script_stream`, `/mcp`, `/healthz`.

Test UIs
- `/docs` (Swagger), `/mcp_ui` (MCP playground), `/start` (interactive UI)

Ports
- Default host/port: `127.0.0.1:7060` (set via `TSM_HOST`, `TSM_PORT`).
- The runner enforces a singleton: it frees the port before starting to avoid stale processes.
