Net-MCP — Quickstart (Scaffold)

Status: Not implemented yet. This page describes intended usage once implemented.

Endpoints
- REST: `POST /actions/<tool>`
- MCP: `POST /mcp` (initialize, tools/list, tools/call)

Runner
- `./Net-MCP/run-tests-and-server.sh` (auto-uses repo .venv if present)

Test UIs
- `/docs` (Swagger) for REST actions
- `/mcp_ui` (MCP playground): initialize, tools/list, tools/call
- `/start` (interactive): http_check, tcp_port_check, dns_resolve/config, resolved_status, proxy checks
