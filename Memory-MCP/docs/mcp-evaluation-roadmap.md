# RoadNerd MCP Evaluation and Roadmap

Purpose
- Define a small‑model–friendly set of HTTP+SSE MCP servers that accelerate RoadNerd’s disambiguation and supplement profiling tests.
- Provide an ordered rollout plan by business value, with specs, evaluation criteria, and integration notes for the Reusable MCPs team.

Guiding Principles
- Small‑model operable (3B/13B): one tool per turn, tiny schemas, strict JSON, short outputs.
- Read‑only, fast, safe: 1–3s timeouts, no `sudo`, truncate big outputs, guard with allowlists.
- HTTP + SSE only: consistent `/healthz`, `/actions/<tool>`, `/sse/<tool_stream>` patterns.
- Attach‑on‑request: start with no tools; model asks for one; orchestrator attaches and calls it.

Rollout (Order by Value)
1) NetworkDiag MCP (Phase 1, highest ROI)
   - Why: Unblocks most “internet not working” cases quickly (routing vs DNS vs captive portal); shortens triage to ≤3 steps.
   - Tools:
     - POST `/actions/iface_info` → `{ interfaces:[{name,mac,ipv4,ipv6,up}] }`
     - POST `/actions/route_info` → `{ default_gateway:{via,dev}|null, routes:[{dst,via,dev}] }`
     - POST `/actions/dns_resolve` `{ qname, type?='A' }` → `{ qname, answers:[{type,ttl,data}], resolver, error? }`
     - POST `/actions/http_check` `{ url, method?='GET', headers?={}, timeout_ms? }` → `{ url, status, redirects:[{status,location}], headers, timing_ms:{dns,connect,tls,ttfb,total}, tls?:{alpn,cert_expiry_days,hostname_ok} }`
     - POST `/actions/tcp_port_check` `{ host, port }` → `{ host, port, open, connect_ms? }`
     - POST `/actions/captive_portal_check` `{ test_url?='http://neverssl.com' }` → `{ suspected, final_url, redirects:[{status,host}], reason }`
2) Service MCP (Phase 1)
   - Why: Surfaces failing services (NetworkManager, systemd‑resolved) immediately.
   - Tools:
     - POST `/actions/service_status` `{ name }` → `{ name, loaded, active, sub, since, description }`
     - POST `/actions/list_failed_units` `{}` → `{ failed:[{name, since, description}] }`
     - POST `/actions/journal_tail` `{ name, lines?=120 }` → `{ name, lines:["..."], truncated }`
3) Ports/Processes MCP (Phase 1.5)
   - Why: Confirms port conflicts and listeners (e.g., 8080 already in use).
   - Tools:
     - POST `/actions/listening_sockets` `{}` → `{ sockets:[{proto,local,process,pid}] }`
     - POST `/actions/who_uses_port` `{ port }` → `{ port, pids:[{pid,process,cmd}] }`
4) DNS Config MCP (Phase 2)
   - Why: Normalizes DNS mode across distros (resolved vs resolvconf), speeds DNS misconfig triage.
   - Tools:
     - POST `/actions/dns_config_get` `{}` → `{ mode:'resolved|resolvconf|other', servers:[ip], search:[domain] }`
     - POST `/actions/resolved_status` `{}` → `{ running, dnssec?, fallback_dns? }`
5) Storage MCP (Phase 2)
   - Why: Disk‑full is common; give quick, safe direction to largest consumers.
   - Tools:
     - POST `/actions/disk_usage` `{}` → `{ mounts:[{mount,fs,used_gb,total_gb,used_pct}] }`
     - POST `/actions/top_consumers` `{ path, depth?=2, n?=10 }` → `{ path, entries:[{name,size_mb}] }`
6) Proxy/Corp MCP (Phase 3, optional)
   - Why: In corporate networks, proxy/IdP reachability explains many “app won’t load” cases.
   - Tools:
     - POST `/actions/proxy_env_status` `{}` → `{ http_proxy?, https_proxy?, no_proxy? }`
     - POST `/actions/proxy_connectivity_test` `{ url }` → `{ url, via_proxy, status?, error? }`
     - POST `/actions/sso_probe` `{ url }` → `{ url, redirect_chain:[{status,host}], idp_host? }`
     - POST `/actions/openid_config` `{ issuer }` → `{ issuer, ok, endpoints?, error? }`
7) WebCheck MCP (Phase 3, optional)
   - Why: Evidence capture (screenshots) for captive portals/router UIs; opt‑in.
   - Tools:
     - POST `/actions/head` `{ url }` → `{ status, headers, timing_ms }`
     - POST `/actions/tls_info` `{ url }` → `{ issuer, sans, expiry_days, protocol, cipher }`
     - GET `/sse/snapshot?url=...` → `ping`/`message`(JSON summary)/`end`; screenshot artifact path referenced in JSON.

Common API Conventions (HTTP+SSE)
- Health: GET `/healthz` → `{ ok:true, name, version }`
- Actions: POST `/actions/<tool>` with JSON; return 200 typed JSON.
- SSE: GET `/sse/<tool_stream>?…` with events `ping`, `message`(JSON), `end`, `error`.
- Envelope: prefer flat typed JSON; when needed `{ ok, data, error?, meta? }`.
- Inputs: `timeout_ms` (default 2000), `run_id` passthrough.
- Errors: `E_TIMEOUT`, `E_NO_BINARY`, `E_UNSUPPORTED`, `E_DNS_FAIL`, `E_CONN_REFUSED`.
- Security: read‑only commands; allowlists for HTTP targets; mask tokens in logs.

Small‑Model Operation (3B/13B)
- System prompt: “You may call MCP HTTP tools. Return ONLY ONE JSON: {"tool":"<namespace/name>","params":{...}}. No prose.”
- Repair prompt (if invalid): “Output invalid. Return ONLY ONE JSON tool call. Example: {"tool":"dns/resolve","params":{"qname":"example.com"}}.”
- 3B profile: temp 0.2, max_tokens ~80, 1 tool per turn; allow 1 repair.
- 13B profile: same schema; can run 2–3 turns reliably.

Attach‑on‑Request Orchestration
- Start with no MCPs attached. Show short catalog (names + one‑liner).
- Ask: “Which single tool do you need first?”
- When model returns a valid JSON tool call, attach the corresponding HTTP server (if not running) and call `/actions/<tool>`.
- Return JSON result; ask “Next tool?” until a label (wifi/dns/routing/proxy) or step budget (≤3) is reached.
- Log each step (requested_tool, attached, call_ok, duration_ms) to RoadNerd JSONL with `mode: "mcp_triage"`.

Evaluation Plan (supplement to profiling)
- Scenarios: wifi_basic, dns_basic, iface_up_no_net, ambiguous_inet, port_conflict_8080.
- Models: 3B vs 13B vs 20B baseline.
- Runs per scenario:
  1) Baseline (no MCP) → standard classify/brainstorm.
  2) MCP‑assisted triage (≤3 tools) → then brainstorm with category_hint from triage.
- Metrics (append to logs):
  - Valid tool JSON on first try (%), repair count
  - Steps to label (count) and total time
  - Brainstorm idea parsing success and ideas_generated
  - Tool error/timeout rates
- Targets:
  - ≥95% valid tool JSON on first try (≤1 repair/5 calls)
  - ≤3 steps to confident label for routing/DNS/captive portal
  - ≥30% reduction in time to label vs baseline
  - ≥15% improvement in idea parsing success when category_hint is set

Deliverables for Reusable MCPs Team
- Phase 1 (start here):
  - NetworkDiag MCP: iface_info, route_info, dns_resolve, http_check, tcp_port_check, captive_portal_check
  - Service MCP: service_status, list_failed_units (+ journal_tail if easy)
  - Ports MCP: who_uses_port (listening_sockets if easy)
- Phase 2:
  - DNS Config MCP: dns_config_get, resolved_status
  - Storage MCP: disk_usage, top_consumers
- Phase 3 (optional, gated by allowlists):
  - Proxy/Corp MCP, WebCheck MCP
- For each server: README with curl examples, JSON schemas, envs (timeouts, allowlists), and SSE event names.

Example Schemas (quick refs)
- route_info → `{ "default_gateway": {"via":"192.168.1.1","dev":"wlp3s0"} | null, "routes":[{"dst":"default","via":"192.168.1.1","dev":"wlp3s0"}] }`
- dns_resolve → `{ "qname":"example.com", "resolver":"192.168.1.1", "answers":[{"type":"A","ttl":123,"data":"93.184.216.34"}], "error"?:"E_DNS_FAIL" }`
- http_check → `{ "url":"http://neverssl.com", "status":301, "redirects":[{"status":301,"location":"http://example.org"}], "timing_ms":{"dns":8,"connect":14,"tls":0,"ttfb":120,"total":180}, "tls"?:{"alpn":"http/1.1","cert_expiry_days":120,"hostname_ok":true} }`

Risks & Mitigations
- Small‑model formatting drift → strict one‑call JSON prompt + one repair retry + validator.
- Environment variability (no nmcli/systemctl) → return `E_NO_BINARY` with a helpful message, do not crash.
- Overreach (POST/DELETE) → servers implement only read‑only checks; reject mutating actions with `E_UNSUPPORTED`.
- Privacy in corp mode → allowlists/blocklists; redact headers; do not store secrets.

Timeline (suggested)
- Week 1: NetworkDiag + Service + who_uses_port — implement + basic tests + curl READMEs
- Week 2: DNS Config + Storage — implement + tests
- Week 3: Run evaluation matrix on 3B/13B/20B, report results, decide on productionizing an opt‑in “Fast Triage” mode

Integration Notes
- Use the same HTTP+SSE pattern as Code‑Log‑Search MCP (already in this repo) for faster team lift.
- In Serena/orchestrator: attach servers on demand when the tool is first requested; pass through `timeout_ms` and `run_id` when provided.

Contacts / Handoff
- RoadNerd: this doc is the current source of truth for scope and priorities.
- Reusable MCPs Team: please start with Phase 1 servers and share prototypes + JSON samples for early feedback; we’ll plug them into Serena for attach‑on‑request trials with 3B/13B models.

