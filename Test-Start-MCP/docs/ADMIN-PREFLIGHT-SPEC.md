# Test‑Start‑MCP — Pre‑Flight + Admin + Profiles (Spec)

## 1) Goals
- Pre‑flight before execution (no “try‑fail‑approve”).
- Runtime policy changes without restart; explicit, TTL‑bound rules.
- Profiles (tester/reviewer/developer/architect) to keep config safe + ergonomic.
- Strong security: scoped rules, TTLs, audits, admin token, origin/CSRF.

## 2) Env
- `TSM_ADMIN_TOKEN` (required for admin API/UI)
- `TSM_ALLOWED_FILE=/path/to/allowlist.json` (runtime rules; persisted)
- `TSM_REQUIRE_PREFLIGHT=0|1` (enforce recent preflight per session)
- Existing: `TSM_ALLOWED_ROOT`, `TSM_ALLOWED_ARGS`, logging vars, host/port

## 3) Policy Model (allowlist.json)
```jsonc
{
  "version": 1,
  "rules": [
    {
      "id": "rule-abc123",
      "type": "path" | "scope",
      "path": "/abs/path/script.sh",
      "scopeRoot": "/abs/project/root",
      "patterns": ["run-tests-and-server.sh","scripts/*.sh"],
      "flagsAllowed": ["--no-tests","--smoke","--kill-port"],
      "flagsDenied": [],
      "caps": {"maxTimeoutMs":90000,"maxBytes":262144,"maxStdoutLines":1500,"concurrency":2},
      "conditions": {"agents":[{"name":"Gemini Pro","version":">=1.0 <2.0"}],"sessions":["sess-uuid"]},
      "ttlSec": 604800,
      "label": "Docker runner",
      "note": "smoke runs",
      "createdBy": "admin",
      "createdAt": "ISO",
      "expiresAt": "ISO"
    }
  ],
  "profiles": {
    "tester":    {"caps":{"maxTimeoutMs":10000,"maxBytes":65536,"maxStdoutLines":200,"concurrency":1},"flagsAllowed":["--no-tests","--smoke"]},
    "reviewer":  {"caps":{"maxTimeoutMs":30000,"maxBytes":131072,"maxStdoutLines":500,"concurrency":1},"flagsAllowed":["--no-tests","--smoke","--kill-port"]},
    "developer": {"caps":{"maxTimeoutMs":90000,"maxBytes":262144,"maxStdoutLines":1500,"concurrency":2},"flagsAllowed":["--no-tests","--smoke","--kill-port","--host","--port"]},
    "architect": {"caps":{"maxTimeoutMs":180000,"maxBytes":524288,"maxStdoutLines":3000,"concurrency":3},"flagsAllowed":["--no-tests","--smoke","--kill-port","--host","--port"]}
  },
  "overlays": [
    {"sessionId":"sess-uuid","profile":"reviewer","expiresAt":"ISO"}
  ]
}
```

## 4) Evaluation (order)
1. Boundary: path under `TSM_ALLOWED_ROOT`; args in `TSM_ALLOWED_ARGS`.
2. Merge sources (highest first): overlays (session) → agent‑conditioned rules → global rules.
3. Match: path exact (type=path) or `scopeRoot` + `patterns` (type=scope).
4. Enforce caps: clamp timeout/bytes/stdout/concurrency; intersect flags with global allowlist.
5. If `TSM_REQUIRE_PREFLIGHT=1`, reject run_script unless a recent preflight exists for this session/path/args.

## 5) APIs
### MCP Tools
- `check_script`
  - In: `{ path, args? }`
  - Out: `{ allowed, reasons[], matchedRule?, suggestions:[{type,value,comment}], adminLink }`
- `run_script` / `list_allowed` (existing)

### REST
- `POST /actions/check_script` → same as MCP tool
- Admin (require `TSM_ADMIN_TOKEN`)
  - `GET /admin` → HTML UI
  - `GET /admin/state` → `{ rules, overlays, profiles }`
  - `POST /admin/allowlist/add` → add rule (path or scope+patterns) with TTL
  - `POST /admin/allowlist/remove` → remove rule
  - `POST /admin/session/profile` → assign profile overlay to `sessionId` with TTL
  - `POST /admin/reload` → reload file (optional if no watcher)

Session identity
- Provide `X-TSM-Session` header with REST, SSE, and MCP requests to associate preflights and enforcement with a session.

## 6) Admin UI
- Panels: Profiles (tester/reviewer/developer/architect), Add Rule (Path or Scope+Patterns + TTL + flags info), Active Rules, Session Overlays, Audit tails.
- `/admin/new?path=…&ttlSec=…` pre‑fills Add Rule with best minimal scope+pattern suggestion.
- Security: admin token, origin checks, anti‑CSRF; canonicalize paths.

## 7) Auditing & Logging
- Execution audit (existing): exec‑YYYYMMDD.jsonl.
- Policy audit (new): policy‑YYYYMMDD.jsonl for add/remove/overlay.
- Optional app logs: `TSM_LOG_DIR|FILE|TS|ROTATE|BACKUPS`.

## 8) Workflow (Agent + Human)
1. Agent calls `check_script` before `run_script`.
2. If not allowed → present `adminLink` and suggestions (no in‑band approval prompts).
3. Human opens `/admin`, adds a minimal, TTL‑bound rule (or assigns profile overlay).
4. Agent re‑checks → runs; results include `logPath` for audit.

## 9) Implementation Plan
- Phase 1: `check_script`; load/save `TSM_ALLOWED_FILE`; policy audit; admin JSON; minimal `/admin`.
- Phase 2: session overlays + profiles; `TSM_REQUIRE_PREFLIGHT` option; UI to assign profile to session.
- Phase 3: `/admin/new` prefill; optional sha256 verification; discovery helper; more tests.

## 10) Test Cases
- Preflight allow/deny; suggestions present.
- Add rule (path + TTL) → run ok; auto‑expire.
- Add rule (scope+patterns) → run ok; flags narrowed; caps enforced.
- Session overlay (profile) for `sessionId` → honored; expires.
- `TSM_REQUIRE_PREFLIGHT=1` → run_script rejected without preflight.
- Admin UI auth + path canonicalization under `TSM_ALLOWED_ROOT`.
