# Git-My-Way-MCP — SPEC (Draft)

Purpose
- Uniform, safe git workflows via MCP tools; standardize commit/push/PR with guardrails (dry-run, require-clean, branch policy).

Tools (MCP)
- repo_status → `{ branch, ahead, behind, dirty, staged, untracked, remotes }`
- branch_list → `{ branches:[{name,current?}], remotes:[{name,heads:[...]}] }`
- create_branch `{ name, from?: string, checkout?: boolean }` → `{ name, created, checkedOut }`
- switch_branch `{ name }` → `{ name, success }`
- diff `{ revspec?: string, staged?: boolean, pathspecs?: string[] }` → `{ patch }` (truncated with logPath when large)
- stage_files `{ paths: string[] }` → `{ staged:[string] }`
- unstage_files `{ paths: string[] }` → `{ unstaged:[string] }`
- prepare_commit `{ message, signoff?: boolean, allowEmpty?: boolean, dryRun?: boolean }` → `{ wouldCommit:{ summary } }`
- commit `{ message, signoff?: boolean, allowEmpty?: boolean, requireClean?: boolean }` → `{ commit:{ sha, summary } }`
- push `{ remote?: string, branch?: string, setUpstream?: boolean, forceWithLease?: boolean }` → `{ remote, branch, pushed }`
- open_pr `{ base, head, title, body }` → `{ url }` (optional; provider via env; may be stub initially)

HTTP Endpoints (planned)
- `POST /actions/<tool>` for each tool
- `POST /mcp` (initialize, tools/list, tools/call)
- `GET /docs`, `/mcp_ui`

Security & Policy
- Operate within a configured repo root only (`GMW_REPO_ROOT`); resolve and validate all paths.
- No destructive defaults: `requireClean` on commit unless overridden; `forceWithLease` only.
- Dry-run support for prepare_commit; confirmation recommended for commit/push.
- Auth for PR creation via env (e.g., GH token), or leave open_pr as stub initially.

Config (env)
- `GMW_REPO_ROOT=/home/alex/Projects/Reusable-MCP`
- `GMW_LOG_DIR=Git-My-Way-MCP/logs`, `GMW_LOG_LEVEL=INFO|DEBUG`
- `GMW_PROVIDER=github|gitlab` for open_pr (optional)

Logging & Audit
- JSONL per action: `{ ts, tool, args(masked), duration_ms, result: success|error, error? }`

MCP JSON-RPC
- initialize → `{ protocolVersion, capabilities.tools, serverInfo }`
- tools/list → definitions above with JSON Schemas
- tools/call → `{ content, structuredContent, isError }`

Test UIs (planned)
- `/docs` (Swagger)
- `/mcp_ui` playground: initialize, list, call commit/push with dry-run safeguards

Examples
- repo_status: `{ "tool":"git-my-way/repo_status", "params":{} }`
- prepare_commit: `{ "tool":"git-my-way/prepare_commit", "params": { "message":"feat: add X", "dryRun": true } }`

Error Codes
- `E_REPO_FORBIDDEN`, `E_BAD_ARG`, `E_EXEC`, `E_POLICY`, `E_PROVIDER`

