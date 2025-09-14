SysDiag-MCP — Quickstart (Scaffold)

Status: Not implemented yet. This page describes intended usage once implemented.

Endpoints
- REST: `POST /actions/<tool>`
- MCP: `POST /mcp` (initialize, tools/list, tools/call)

Runner
- `./SysDiag-MCP/run-tests-and-server.sh` (auto-uses repo .venv if present)

Test UIs
- `/docs` (Swagger) for REST actions
- `/mcp_ui` (MCP playground): initialize, tools/list, tools/call
- `/start` (interactive): listening_sockets, who_uses_port, os_info, cpu_mem_info, disk_usage, top_consumers
