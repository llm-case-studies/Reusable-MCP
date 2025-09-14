# SysDiag-MCP — SPEC (Draft)

Tools (MCP)
- listening_sockets `{}` → `{ sockets:[{proto,local,process,pid}] }`
- who_uses_port `{ port }` → `{ port, pids:[{pid,process,cmd}] }`
- os_info `{}` → `{ distro, kernel, arch }`
- cpu_mem_info `{}` → `{ cpu:{cores,model}, mem:{total_mb,free_mb}, loadavg:{1m,5m,15m} }`
- disk_usage `{}` → `{ mounts:[{mount,fs,used_gb,total_gb,used_pct}] }`
- top_consumers `{ path, depth?:2, n?:10 }` → `{ path, entries:[{name,size_mb}] }`

HTTP
- `POST /actions/<tool>`; `POST /mcp`; `/mcp_ui`

Security
- psutil-first; read-only; timeouts; path allowlists for top_consumers.

Config (env)
- `SYS_LOG_DIR`, `SYS_TOKEN`

Errors
- `E_NO_BINARY`, `E_TIMEOUT`, `E_FORBIDDEN`, `E_UNSUPPORTED`

