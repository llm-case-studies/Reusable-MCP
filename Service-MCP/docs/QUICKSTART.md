Service-MCP — Quickstart (Scaffold)

Status: Not implemented yet. This page describes intended usage once implemented.

Endpoints
- REST: `POST /actions/<tool>` (service_status, list_failed_units, journal_tail)
- MCP: `POST /mcp` (initialize, tools/list, tools/call)

Runner
- `./Service-MCP/run-tests-and-server.sh` (auto-uses repo .venv if present)

Test UIs
- `/docs` (Swagger) for REST actions
- `/mcp_ui` (MCP playground): initialize, tools/list, tools/call
- `/start` (interactive): service_status form, list_failed_units, journal_tail viewer

Ports
- Default: `127.0.0.1:7040`
- Env (planned): `SVC_HOST`, `SVC_PORT`
