# Integration Guide

This service exposes HTTP/SSE endpoints for cheap, fast search. Any agent can call these actions directly.

## Actions
- POST /actions/search_code → { hits: [{file,line,preview}] }
- GET /sse/search_code_stream?query=…&root=… → SSE streaming of hits
- POST /actions/search_logs → { entries: [...] }
- GET /healthz → { ok, code_root, logs_root }

## Example: curl
```
# Code search
curl -s -X POST http://127.0.0.1:7080/actions/search_code \
  -H 'Content-Type: application/json' \
  -d '{"query":"num_predict","root":"/home/alex/Projects/iHomeNerd","maxResults":10}' | jq .

# Logs search
curl -s -X POST http://127.0.0.1:7080/actions/search_logs \
  -H 'Content-Type: application/json' \
  -d '{"query":"brainstorm","mode":"brainstorm","maxResults":10}' | jq .

# SSE stream
curl -N "http://127.0.0.1:7080/sse/search_code_stream?query=brainstorm&root=/home/alex/Projects/iHomeNerd"
```

## Example: MCP tool registration (Agentic SDK, pseudo-config)
```yaml
# tools.yaml
code_log_search:
  type: http
  baseUrl: http://127.0.0.1:7080
  actions:
    - name: search_code
      method: POST
      path: /actions/search_code
    - name: search_logs
      method: POST
      path: /actions/search_logs
    - name: search_code_stream
      method: GET
      path: /sse/search_code_stream
```

## Example: Node (fetch)
```ts
const base = 'http://127.0.0.1:7080';
async function searchCode(query: string, root: string){
  const r = await fetch(base + '/actions/search_code', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({query, root, maxResults: 50})
  });
  const data = await r.json();
  return data.hits;
}
```

## Example: Python client
```py
import requests
base = 'http://127.0.0.1:7080'
resp = requests.post(base + '/actions/search_code', json={'query':'num_predict','root':'/home/alex/Projects/iHomeNerd'})
print(resp.json())
```

## Security
- Defaults to 127.0.0.1. Add a bearer token (CLS_TOKEN) if exposing beyond localhost (future option).
- Result sizes capped by maxResults; prefer streaming for large queries.

## Systemd user unit
See deploy/code-log-search-mcp.service and enable with systemctl --user.
