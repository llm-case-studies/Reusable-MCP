# Docker-MCP — SPEC (Draft)

Provider
- Supports Docker or Podman via CLI abstraction; select with `DOCKER_MCP_PROVIDER=docker|podman`.

Tools (MCP)
- engine_info → `{ provider, version, rootless?, socket? }`
- images_list → `{ images:[{repository,tag,id,size}] }`
- containers_list → `{ containers:[{id,name,image,status,ports}] }`
- container_inspect `{ idOrName }` → `{ data }`
- container_logs `{ idOrName, tail?:number=100, since?:string, follow?:boolean }` → SSE when follow=true; otherwise `{ lines:["…"], truncated }`
- container_stats `{ idOrName, stream?:boolean }` → SSE when stream=true; otherwise `{ cpu_pct, mem_mb, net:{rx,tx} }`

Mutating (gated by allowlists)
- container_start `{ idOrName }` → `{ started:true }`
- container_stop `{ idOrName, timeout?:number }` → `{ stopped:true }`
- image_pull `{ name, tag?:string }` → `{ pulled:true }` (registries allowlisted)
- container_run `{ image, name?:string, args?:string[], env?:object, ports?:object, volumes?:object }` → `{ id,name }` (highly restricted; default off)

HTTP
- `POST /actions/<tool>`; `GET /sse/<stream>` for logs/stats
- `POST /mcp` (initialize, tools/list, tools/call); `/mcp_ui`

Security & Policy
- Read-only by default; enable mutating ops via explicit env flags.
- Allowlists: image registries, container names/prefixes.
- Forbid `--privileged`; forbid host mounts unless allowlisted.
- Timeouts on long ops; redact secrets in logs; audit JSONL per action.

Config (env)
- `DOCKER_MCP_PROVIDER=docker|podman`
- `DOCKER_MCP_MUTATE=0|1` (default 0)
- `DOCKER_MCP_ALLOWED_REGISTRIES=docker.io,ghcr.io`
- `DOCKER_MCP_ALLOWED_NAMES=app*,service-*`
- `DOCKER_MCP_LOG_DIR=Docker-MCP/logs`, `DOCKER_MCP_LOG_LEVEL=INFO|DEBUG`

Errors
- `E_TIMEOUT`, `E_FORBIDDEN`, `E_NO_BINARY`, `E_EXEC`, `E_POLICY`

