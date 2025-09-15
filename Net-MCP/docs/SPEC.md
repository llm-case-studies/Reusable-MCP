# Net-MCP — SPEC (Draft)

Tools (MCP)
- iface_info → `{ interfaces:[{name,mac,ipv4,ipv6,up}] }`
- route_info → `{ default_gateway:{via,dev}|null, routes:[{dst,via,dev}] }`
- dns_resolve `{ qname, type?: 'A'|'AAAA' }` → `{ qname, answers:[{type,ttl,data}], resolver, error? }`
- http_check `{ url, method?:'GET', headers?:{}, timeout_ms? }` → `{ url, status, redirects:[{status,location}], headers, timing_ms:{dns,connect,tls,ttfb,total}, tls?:{alpn,cert_expiry_days,hostname_ok} }`
- tcp_port_check `{ host, port }` → `{ host, port, open, connect_ms? }`
- captive_portal_check `{ test_url?: 'http://neverssl.com' }` → `{ suspected, final_url, redirects:[{status,host}], reason }`
- dns_config_get `{}` → `{ mode:'resolved|resolvconf|other', servers:[ip], search:[domain] }`
- resolved_status `{}` → `{ running, dnssec?, fallback_dns? }`
- proxy_env_status `{}` → `{ http_proxy?, https_proxy?, no_proxy? }`
- proxy_connectivity_test `{ url }` → `{ url, via_proxy, status?, error? }`
- openid_config `{ issuer }` → `{ issuer, ok, endpoints?, error? }`

HTTP
- `POST /actions/<tool>`; `GET /sse/<stream>` for streaming checks (optional)
- `POST /mcp` (initialize, tools/list, tools/call); `/mcp_ui`

Security
- Read-only commands; timeouts (default 2000ms); allowlist for http_check URLs; no sudo; redact headers/tokens.

Config (env)
- `NET_TIMEOUT_MS_DEFAULT=2000`, `NET_HTTP_ALLOWLIST=neverssl.com,httpbin.org`
- App logging: `NET_LOG_DIR=Net-MCP/logs`, `NET_LOG_FILE=<file>`, `NET_LOG_TS=0|1`, `NET_LOG_ROTATE=<bytes>`, `NET_LOG_BACKUPS=<n>`, `NET_LOG_LEVEL=INFO|DEBUG`, `NET_TOKEN`
- Network: `NET_HOST=127.0.0.1`, `NET_PORT=7030` (default)

Errors
- `E_TIMEOUT`, `E_NO_BINARY`, `E_UNSUPPORTED`, `E_DNS_FAIL`, `E_CONN_REFUSED`

Logging & Audit
- JSONL audit (planned) for key actions under `NET_LOG_DIR` with records like `{ ts, tool, args(masked), duration_ms, status }`.
- Optional app log file as configured via `NET_LOG_DIR`/`NET_LOG_FILE` with rotation options.

## Test UIs
- `/docs` (Swagger) for REST actions (`/actions/*`).
- `/mcp_ui` (MCP playground): initialize, tools/list, tools/call for network diagnostics.
- `/start` (interactive): run http_check, tcp_port_check, dns_resolve/config, resolved_status, proxy_env_status/connectivity; show results and optional streaming outputs where applicable.
