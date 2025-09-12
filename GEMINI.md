# Project Overview

This directory contains a collection of reusable MCP (Modular Control Plane) services, each designed to provide a specific functionality to an AI agent. All services are implemented in Python and use FastAPI to expose a simple HTTP/SSE interface.

The three services are:

*   **Code-Log-Search-MCP**: A lightweight server for searching code and logs using `ripgrep`.
*   **Memory-MCP**: A service that provides durable, project-scoped memory for agents, with a SQLite backend.
*   **Prior-Self-MCP**: A tool that gives agents access to prior chat context across sessions and projects, with a JSONL and SQLite FTS backend.

## Building and Running

Each service has its own set of dependencies and instructions for running.

### Code-Log-Search-MCP

*   **Dependencies**: `fastapi`, `uvicorn`, `pytest`, `ripgrep`
*   **Running**:
    ```bash
    python3 server/app.py --host 127.0.0.1 --port 7080 \
      --default-code-root /path/to/your/code \
      --logs-root /path/to/your/logs
    ```
*   **Testing**:
    ```bash
    pytest -q
    ```

### Memory-MCP

*   **Dependencies**: `fastapi`, `uvicorn`, `pytest`
*   **Running**:
    ```bash
    ./run-tests-and-server.sh --host 127.0.0.1 --port 7090
    ```
    or
    ```bash
    python3 server/app.py --home "$HOME/.roadnerd/memorydb" --host 127.0.0.1 --port 7090
    ```
*   **Testing**:
    ```bash
    pytest -q
    ```

### Gemini CLI integration

Project settings (`.gemini/settings.json`) can configure MCP servers and optional Shell workspaces:

```json
{
  "mcpServers": {
    "memory-mcp": {
      "httpUrl": "http://127.0.0.1:7090/mcp",
      "timeout": 15000,
      "headers": { "Authorization": "Bearer ${MEM_TOKEN}" },
      "description": "Reusable-MCP Memory server (streamable HTTP)"
    }
  },
  "workspaces": {
    "Memory-MCP": "/home/<you>/Projects/Reusable-MCP/Memory-MCP"
  }
}
```

- The workspace mapping lets Gemini’s Shell tool run project scripts like `run-tests-and-server.sh` without absolute paths.
- For HTTP-only integration (no Shell), just keep the server running and configure `httpUrl` as above.

### Dev script (pattern)

Each MCP can ship a test+server runner similar to `Memory-MCP/run-tests-and-server.sh`:
- Flags: `--no-tests`, `--clean-home`, `--kill-port`, `--smoke` (healthz + MCP init/list + write/read).
- Logs: set `MEM_LOG_DIR` (appends by default). Use `MEM_LOG_TS=1` to timestamp filenames.

### Prior-Self-MCP

*   **Dependencies**: `fastapi`, `uvicorn`, `pytest`
*   **Setup**:
    ```bash
    export PRIOR_SELF_HOME="$HOME/.roadnerd/chatdb"
    mkdir -p "$PRIOR_SELF_HOME/transcripts"
    ```
*   **Ingest**:
    ```bash
    python3 ingest/append.py --chat-id session_1 --project RoadNerd \
      --role assistant --text "Your chat message"
    ```
*   **Index**:
    ```bash
    python3 indexer/build_index.py --home "$PRIOR_SELF_HOME"
    ```
*   **Running**:
    ```bash
    python3 server/app.py --home "$PRI_SELF_HOME" --host 127.0.0.1 --port 7070
    ```
*   **Testing**:
    ```bash
    # Not specified, but likely `pytest -q`
    ```

## Development Conventions

*   All services are written in Python 3.10+.
*   They use FastAPI for the web server.
*   Each service has its own virtual environment (e.g., `.mcp-venv` in `Memory-MCP`).
*   Each service has a `docs` directory with `QUICKSTART.md`, `SPEC.md`, and other documentation.
*   Each service has a `tests` directory with pytest tests.
*   Each service has a `deploy` directory with a systemd service file.
