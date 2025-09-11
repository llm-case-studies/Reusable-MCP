# Code-Log-Search-MCP Quickstart

## Requirements
- Python 3.10+
- ripgrep (`rg`) installed and on PATH
- `pip install fastapi uvicorn pytest`

## Run the server
```
python3 server/app.py --host 127.0.0.1 --port 7080 \
  --default-code-root /home/alex/Projects/iHomeNerd \
  --logs-root "$HOME/.roadnerd/logs"
```

## Health check
```
curl -s http://127.0.0.1:7080/healthz
```

## Actions
- search_code (POST /actions/search_code)
```
curl -s -X POST http://127.0.0.1:7080/actions/search_code \
  -H 'Content-Type: application/json' \
  -d '{"query":"num_predict","root":"/home/alex/Projects/iHomeNerd","maxResults":5,"contextLines":1}' | jq .
```

- search_logs (POST /actions/search_logs)
```
curl -s -X POST http://127.0.0.1:7080/actions/search_logs \
  -H 'Content-Type: application/json' \
  -d '{"query":"brainstorm","mode":"brainstorm","maxResults":10}' | jq .
```

- SSE stream (GET /sse/search_code_stream?query=…&root=…)
```
curl -N "http://127.0.0.1:7080/sse/search_code_stream?query=brainstorm&root=/home/alex/Projects/iHomeNerd"
```

## Run tests
```
pytest -q
```
