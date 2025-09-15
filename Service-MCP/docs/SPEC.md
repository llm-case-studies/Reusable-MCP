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
- `SVC_TIMEOUT_MS_DEFAULT=2000`, `SVC_MAX_LINES=120`
- App logging: `SVC_LOG_DIR=Service-MCP/logs`, `SVC_LOG_FILE=<file>`, `SVC_LOG_TS=0|1`, `SVC_LOG_ROTATE=<bytes>`, `SVC_LOG_BACKUPS=<n>`, `SVC_LOG_LEVEL=INFO|DEBUG`, `SVC_TOKEN`
- Network: `SVC_HOST=127.0.0.1`, `SVC_PORT=7040` (default)

Errors
- `E_NO_BINARY` (no systemctl/journalctl), `E_TIMEOUT`, `E_UNSUPPORTED`

Logging & Audit
- JSONL audit (planned) under `SVC_LOG_DIR` for actions like service_status and journal_tail.
- Optional app log file as configured via `SVC_LOG_DIR`/`SVC_LOG_FILE` with rotation options.

## Test UIs
- `/docs` (Swagger) for REST actions (`/actions/*`).
- `/mcp_ui` (MCP playground): initialize, tools/list, tools/call for service diagnostics.
- `/start` (interactive): service_status (form), list_failed_units, journal_tail (textarea output). Read‑only by default.
