# Memory-MCP Quickstart

## Requirements
- Python 3.10+
- `pip install fastapi uvicorn pytest`

## Run the server
```
./run-tests-and-server.sh --host 127.0.0.1 --port 7090
# or
python3 server/app.py --home "$HOME/.roadnerd/memorydb" --host 127.0.0.1 --port 7090
```

## Health
```
curl -s http://127.0.0.1:7090/healthz
```

## Actions
- Write:
```
curl -s -X POST http://127.0.0.1:7090/actions/write_memory \
  -H 'Content-Type: application/json' \
  -d '{"project":"RoadNerd","scope":"project","key":"prompt_policy","text":"Dynamic tokens: max(512,n*120)","tags":["decision","prompt" ]}' | jq .
```

- Search:
```
curl -s -X POST http://127.0.0.1:7090/actions/search_memory \
  -H 'Content-Type: application/json' \
  -d '{"query":"tokens","project":"RoadNerd","k":5}' | jq .
```

- Read:
```
curl -s -X POST http://127.0.0.1:7090/actions/read_memory \
  -H 'Content-Type: application/json' \
  -d '{"project":"RoadNerd","key":"prompt_policy"}' | jq .
```

## Tests
```
pytest -q
```

## Systemd (user) service
```
mkdir -p ~/.config/systemd/user
cp deploy/memory-mcp.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now memory-mcp.service
```
