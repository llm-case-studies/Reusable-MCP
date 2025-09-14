# Service-MCP — SPEC (Draft)

Tools (MCP)
- service_status `{ name }` → `{ name, loaded, active, sub, since, description }`
- list_failed_units `{}` → `{ failed:[{name, since, description}] }`
- journal_tail `{ name, lines?: number=120 }` → `{ name, lines:["..."], truncated }`

HTTP
- `POST /actions/<tool>`; `POST /mcp`; `/mcp_ui`

Security
- Read-only diagnostics; timeouts; redact sensitive content from logs.

Config (env)
- `SVC_TIMEOUT_MS_DEFAULT=2000`, `SVC_MAX_LINES=120`, `SVC_LOG_DIR`, `SVC_TOKEN`

Errors
- `E_NO_BINARY` (no systemctl/journalctl), `E_TIMEOUT`, `E_UNSUPPORTED`

## Test UIs
- `/docs` (Swagger) for REST actions (`/actions/*`).
- `/mcp_ui` (MCP playground): initialize, tools/list, tools/call for service diagnostics.
- `/start` (interactive): service_status (form), list_failed_units, journal_tail (textarea output). Read‑only by default.
