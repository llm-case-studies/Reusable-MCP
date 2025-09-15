Test-Start-MCP — Test Plan (Gemini + E2E)

Scope
- Validate safe execution with allowlists, timeouts, truncation, SSE streaming, and audit logging.
- Cover both MCP tools and HTTP REST/SSE endpoints.

Environment
- Server: `./Test-Start-MCP/run-tests-and-server.sh` (singleton, frees port)
- Defaults: `TSM_HOST=127.0.0.1`, `TSM_PORT=7060`.
- Policy: `TSM_ALLOWED_ROOT`, `TSM_ALLOWED_SCRIPTS`, `TSM_ALLOWED_ARGS` (set by runner).
- Logging: `TSM_LOG_DIR` (audit JSONL + optional app log), `TSM_LOG_FILE`, `TSM_LOG_TS`, `TSM_LOG_ROTATE`, `TSM_LOG_BACKUPS`.
- Optional: `TSM_TOKEN` for auth.

MCP (Gemini) — Required cases
1) initialize → protocolVersion == 2025-06-18
2) tools/list → contains `run_script` and `list_allowed`
3) run_script (probe.py) → exitCode 0, duration_ms present, stdout/stderr, logPath present
4) list_allowed → includes runner + probe scripts; flags include probe options
5) Forbidden path (/bin/echo) → structured error (E_FORBIDDEN)
6) Bad args (positional) → structured error (E_BAD_ARG)
7) Truncation (probe.py --bytes large) → truncated:true
8) Timeout (probe.py slow vs low timeout_ms) → exitCode -1, stderr: timeout

REST/SSE — Optional cases
9) POST /actions/run_script (probe.sh) → 200, stdout/stderr
10) GET /sse/run_script_stream (probe.sh) → stdout/stderr events and end (args as JSON array)
11) POST /actions/get_stats → counters reflect new runs
12) GET /healthz → ok:true, checks set

Artifacts
- Audit JSONL under `Test-Start-MCP/logs/exec-YYYYMMDD.jsonl` (logPath in results)
- App logs when enabled via TSM_LOG_* vars

