# Test‑Start‑MCP — Policy, Pre‑flight, Roles (Roadmap)

This document captures our current implementation, constraints discovered in practice, and the plan to make policy and pre‑flight work reliably across platforms (Gemini, Codex, etc.).

## Motivation
- Platforms often hide `initialize` results and HTTP headers from the model.
- Models are stateless; they may not bootstrap a session unless a planner forces it.
- The human must retain control — approvals are human‑only and audited.
- We need “check before run” to hold regardless of client quirks, and give agents human‑actionable guidance inline.

## Shipped Now
- Tools and guidance
  - `check_script` returns `allowed`, `reasons`, `suggestions`, and an absolute `adminLink` with a pasteable `responseTemplate`.
  - `start_here` tool returns the same guidance for platforms that hide `initialize`.
  - `tools/list` adds x-guidance hints (use `check_script` before `run_script`).
  - `initialize` (if surfaced) embeds `policy.preflight`, `allowedRoot`, and instructions.
- Preflight token (Phase A)
  - When `allowed=true`, `check_script` returns `{ preflightToken, expiresAt }`.
  - `run_script` (MCP + REST) and SSE accept optional `preflight_token`.
  - When `TSM_REQUIRE_PREFLIGHT=1`, server enforces that a valid `preflight_token` or a legacy session preflight exists; otherwise returns guidance with `adminLink` and `responseTemplate`.
- Enforcement (optional)
  - `TSM_REQUIRE_PREFLIGHT=1` enforces “check → run” using a simple in‑memory cache keyed by session header (for our UI).
- Admin & audit
  - Add/remove rules (Path vs Scope), Assign Profile Overlay, policy audit tail.
  - Execution audit (exec-YYYYMMDD.jsonl).
  - Request/access audit (access-YYYYMMDD.jsonl) of REST/MCP calls (sanitized).
- UI refactor
  - All UIs use templates and static assets for easy debugging.

## Key Changes for Platforms
- Agents will always see absolute admin links and pasteable response templates in `check_script` (and later in `run_script` errors) — no need to read docs or headers.
- Optional session overlays remain for our UIs; we avoid hard reliance on headers for third‑party clients.

## Plan (Phased)

### Phase A — Preflight Token (Implemented)
- `check_script` now returns `{ preflightToken, expiresAt }` (HMAC‑signed, bound to `{ path, args[] }`).
- `run_script` (MCP + REST) and SSE accept `preflight_token`; if `TSM_REQUIRE_PREFLIGHT=1` and token missing/invalid/expired/mismatch → server rejects with user‑facing guidance (absolute `adminLink` + `responseTemplate`).
- Rationale: Platforms reliably pass arguments; this enforces “check before run” without `initialize` or headers.

Token format
- Compact JWT‑style: base64url(header).base64url(payload).base64url(HMAC‑SHA256).
- Header: `{ alg: "HS256", typ: "JWT" }`.
- Payload: `{ p: <abs canonical path>, ah: sha256(JSON.stringify(args)), iat, exp, v:1 }`.
- Secret: `TSM_PREFLIGHT_SECRET` (ephemeral fallback with warning when enforcement is on).

### Phase B — Human‑managed overlays (in progress)
- Admin UI: “Generate Session ID for Role” — implemented
  - New panel on `/admin` to generate a session id, choose a profile and TTL, and assign an overlay; supports selectors.
- Tools accept `sessionId` and optional `role` in arguments — implemented
  - MCP: `check_script(..., sessionId?, role?)`, `run_script(..., sessionId?, role?, preflight_token?)`.
  - REST/SSE also accept `sessionId` (body/query) in addition to `X-TSM-Session` header.
- Overlays with selectors — implemented
  - Overlay dataclass extended with optional `path`, `scopeRoot`, `patterns`.
  - Evaluation priority: overlay‑path > overlay‑scope > overlay‑session (no selector) > rule > globals.
  - Caps clamping and flag intersections honor the selected overlay.

### Phase C — Principal overlays (longer term)
- Overlays keyed by Authorization token fingerprint (“principal”) for real clients.
- Admin: “Apply to” radio → Principal | Session | Global.

## Admin UI Polish
- Tabs or radios: Path Rule | Scope Rule (hide irrelevant fields in each mode).
- Show Allowed Root (TSM_ALLOWED_ROOT) chip; disable Add if outside root.
- Suggestions when `?path=…` present (prefill scope root + basename pattern).
- TTL presets (600/3600/86400). Optional “Validate” button (read‑only call to `check_script`).

## Roles (Practical & Safe)
- `role` arg in tools is for audit and hints; it does not widen privileges.
- Overlays define effective permissions:
  - Flags: global ∩ overlay.flagsAllowed ∩ rule.flagsAllowed (minus denied).
  - Caps: clamp timeout/output to min(overlay.caps, rule.caps).
- Default when no `sessionId` provided: your chosen default during testing (later safer default or mandatory preflight).

## Settings & Hints
- `.gemini/settings.json` can include a non‑binding `hints` block for humans/wrappers (roles, response templates). It does not change model behavior.
 - New env: `TSM_PREFLIGHT_SECRET` to sign tokens (recommended when `TSM_REQUIRE_PREFLIGHT=1`).

## Security & Logging
- Boundaries: Always enforce `TSM_ALLOWED_ROOT` and path canonicalization.
- Audits: `exec-YYYYMMDD.jsonl` (execution), `policy-YYYYMMDD.jsonl` (admin mutations), `access-YYYYMMDD.jsonl` (requests; sanitized).
- No secrets logged (Authorization/Cookie are scrubbed in access logs).

## Compatibility
- All changes are additive; preflight_token, sessionId, and role are optional tool arguments.
- In‑memory session preflight cache remains for our UIs; token enforcement is the agent‑agnostic mechanism.
 - With `TSM_REQUIRE_PREFLIGHT=0`, tokens are optional and not enforced; existing flows remain unchanged.

## Test & Validate
- Playwright MCP: run with `--isolated` to avoid Chrome profile locks.
- Flows:
  - `/mcp_ui`: initialize → tools/list → start_here → check_script → run_script (with preflight_token in Phase A).
  - `/start`: list_allowed → run_script (REST) → SSE → logs → stats/health.
  - `/admin`: add path/scope rule, remove rule, Assign Profile Overlay (Generate Session ID), audit tail.
- Examine `access-YYYYMMDD.jsonl` to see what arguments platforms send (e.g., sessionId, role).

## Quick Reference
- Env: `TSM_ALLOWED_ROOT`, `TSM_ALLOWED_SCRIPTS`, `TSM_ALLOWED_ARGS`, `TSM_ADMIN_TOKEN`, `TSM_REQUIRE_PREFLIGHT`, `TSM_PREFLIGHT_TTL_SEC`, `TSM_LOG_DIR`.
- Endpoints: `/mcp`, `/mcp_ui`, `/start`, `/admin`, `/admin/state`, `/admin/allowlist/add|remove`, `/admin/session/profile`, `/sse/run_script_stream`, `/actions/*`.
- Logs: `exec-YYYYMMDD.jsonl`, `policy-YYYYMMDD.jsonl`, `access-YYYYMMDD.jsonl` under `TSM_LOG_DIR`.

## Next Work Items (to resume)
1) Phase B: add optional `sessionId` param to MCP tools; Admin “Generate Session ID for Role”; overlays with path/scope selectors; UI tabs (Path/Scope).
2) Optional: principal overlays (by token fingerprint), and preflight read‑only audit entries.
