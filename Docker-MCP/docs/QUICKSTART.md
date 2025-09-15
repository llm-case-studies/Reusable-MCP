Docker-MCP — Quickstart (Scaffold)

Status: Not implemented yet. This page describes intended usage once implemented.

Endpoints
- REST: `POST /actions/<tool>`
- MCP: `POST /mcp` (initialize, tools/list, tools/call)

Runner
- `./Docker-MCP/run-tests-and-server.sh` (auto-uses repo .venv if present)

Test UIs
- `/docs` (Swagger) for REST actions
- `/mcp_ui` (MCP playground): initialize, tools/list, tools/call
- `/start` (interactive): images/containers list, inspect, logs (SSE), stats (SSE); gated start/stop when enabled

Ports
- Default: `127.0.0.1:7020`
- Env (planned): `DOCKER_MCP_HOST`, `DOCKER_MCP_PORT`
