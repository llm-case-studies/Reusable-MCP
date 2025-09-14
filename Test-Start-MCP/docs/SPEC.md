# Test‑Start‑MCP — SPEC (Draft)

Purpose
- Safely start and smoke‑test local MCP services from models when their sandboxes can’t run scripts.
- Execute only explicitly allowed scripts with validated args; stream output; provide audit logs.

Tools (MCP)
- run_script
  - Input: `{ path: string, args?: string[], env?: object, timeout_ms?: number }`
  - Output: `{ exitCode: number, duration_ms: number, stdout?: string, stderr?: string, truncated?: boolean, logPath?: string }`
  - Behavior: Runs script if path and args pass policy. No shell. Returns when process exits (or times out).
- run_script_stream (SSE)
  - Endpoint: `GET /sse/run_script_stream?path=…&args=…&timeout_ms=…`
  - Events: `ping {t}`, `stdout {line}`, `stderr {line}`, `end {exitCode,duration_ms,truncated?}`, `error {code,message}`
- list_allowed
  - Input: `{}`
  - Output: `{ scripts: [{ path, allowedArgs: [string], defaultArgs?: [string] }] }`

HTTP Endpoints (planned)
- `POST /actions/run_script` → run_script
- `POST /actions/list_allowed` → list_allowed
- `GET /sse/run_script_stream` → stream stdout/stderr/end/error
- `GET /healthz` → `{ ok: true, name, version }`

Security & Policy
- Allowlist (minimal, explicit)
  - `TSM_ALLOWED_SCRIPTS` (colon/semicolon separated):
    - `/home/alex/Projects/Reusable-MCP/Memory-MCP/run-tests-and-server.sh`
    - `/home/alex/Projects/Reusable-MCP/Code-Log-Search-MCP/run-tests-and-server.sh`
    - `/home/alex/Projects/Reusable-MCP/Prior-Self-MCP/run-tests-and-server.sh`
  - `TSM_ALLOWED_ROOT=/home/alex/Projects/Reusable-MCP` (scripts must resolve under it)
  - `TSM_ALLOWED_ARGS=--no-tests,--kill-port,--smoke,--host,--port,--default-code-root,--logs-root,--home`
  - `TSM_ENV_ALLOWLIST=CLS_TOKEN,PRIOR_TOKEN,MEM_TOKEN`
- Execution
  - No shell: exec argv only; cwd = script folder; add `--` when appropriate.
  - Validate path + args; numeric arg coercion for known flags.
  - Timeout enforced; kill on expiry; truncate stdout/stderr; structured errors.
- Auth
  - Optional bearer token `TSM_TOKEN` for all endpoints.

Config (env)
- `TSM_ALLOWED_ROOT`, `TSM_ALLOWED_SCRIPTS`, `TSM_ALLOWED_ARGS`, `TSM_ENV_ALLOWLIST`
- `TSM_TIMEOUT_MS_DEFAULT=90000`, `TSM_MAX_OUTPUT_BYTES=262144`, `TSM_MAX_LINE_BYTES=8192`
- `TSM_LOG_DIR=Test-Start-MCP/logs`, `TSM_LOG_LEVEL=INFO|DEBUG`

Logging & Audit
- JSONL: `{ ts, tool, path, args, duration_ms, exitCode, result, truncated, requester? }`
- File logging under `TSM_LOG_DIR`.

MCP JSON‑RPC
- initialize → `{ protocolVersion, capabilities.tools, serverInfo }`
- tools/list → definitions for `run_script`, `list_allowed` (reference `run_script_stream` under SSE)
- tools/call → returns `{ content, structuredContent, isError }`

Test UIs (planned)
- `/docs` (Swagger) for REST
- `/mcp_ui` (MCP playground): initialize, list, run_script

Attach‑on‑Request
- If the model requests `test-start/run_script`, attach server and call it. Prefer SSE for live output.

Examples
- Start CLS runner (90s budget):
```
{
  "tool": "test-start/run_script",
  "params": {
    "path": "/home/alex/Projects/Reusable-MCP/Code-Log-Search-MCP/run-tests-and-server.sh",
    "args": ["--kill-port", "--smoke"],
    "timeout_ms": 90000
  }
}
```
- List allowed: `{ "tool": "test-start/list_allowed", "params": {} }`

Error Codes
- `E_FORBIDDEN`, `E_BAD_ARG`, `E_TIMEOUT`, `E_EXEC`, `E_POLICY`

