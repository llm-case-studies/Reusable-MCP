# Code-Log-Search-MCP Quickstart

## Requirements
- Python 3.10+
- ripgrep (`rg`) installed and on PATH
- `pip install fastapi uvicorn pytest`

## Run the server
Option A: Dev script (edit defaults, then run)
The script has a config block at the top. Defaults:
- `HOST=127.0.0.1`, `PORT=7080`
- `CODE_ROOT` defaults to the repository root
- `LOGS_ROOT` defaults to `Code-Log-Search-MCP/logs`
- Flags: `NO_TESTS=0`, `KILL_PORT=1`, `SMOKE=1`
You can also create `Code-Log-Search-MCP/.env` to override, or pass CLI flags.

```
./run-tests-and-server.sh         # runs tests + smoke + serve with defaults
./run-tests-and-server.sh --help  # show flags and config info
```

Option B: Direct
```
python3 server/app.py --host 127.0.0.1 --port 7080 \
  --default-code-root "$PWD" \
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
