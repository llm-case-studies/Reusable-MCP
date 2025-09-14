# NetworkDiag-MCP — SPEC (Draft)

Tools (MCP)
- iface_info → `{ interfaces:[{name,mac,ipv4,ipv6,up}] }`
- route_info → `{ default_gateway:{via,dev}|null, routes:[{dst,via,dev}] }`
- dns_resolve `{ qname, type?: 'A'|'AAAA' }` → `{ qname, answers:[{type,ttl,data}], resolver, error? }`
- http_check `{ url, method?:'GET', headers?:{}, timeout_ms? }` → `{ url, status, redirects:[{status,location}], headers, timing_ms:{dns,connect,tls,ttfb,total}, tls?:{alpn,cert_expiry_days,hostname_ok} }`
- tcp_port_check `{ host, port }` → `{ host, port, open, connect_ms? }`
- captive_portal_check `{ test_url?: 'http://neverssl.com' }` → `{ suspected, final_url, redirects:[{status,host}], reason }`

HTTP
- `POST /actions/<tool>`; `GET /sse/<stream>` for streaming checks (optional)
- `POST /mcp` (initialize, tools/list, tools/call); `/mcp_ui`

Security
- Read-only commands; timeouts (default 2000ms); allowlist for http_check URLs; no sudo.

Config (env)
- `ND_TIMEOUT_MS_DEFAULT=2000`, `ND_HTTP_ALLOWLIST=neverssl.com,httpbin.org`, `ND_LOG_DIR`, `ND_TOKEN`

Errors
- `E_TIMEOUT`, `E_NO_BINARY`, `E_UNSUPPORTED`, `E_DNS_FAIL`, `E_CONN_REFUSED`

