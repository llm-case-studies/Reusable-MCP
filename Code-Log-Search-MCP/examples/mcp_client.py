#!/usr/bin/env python3
import json
import os
from pathlib import Path
from typing import Any, Dict

import requests


BASE = os.environ.get("CLS_URL", "http://127.0.0.1:7080/mcp")


def post(payload: Dict[str, Any]):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    r = requests.post(BASE, headers=headers, data=json.dumps(payload))
    r.raise_for_status()
    return r.json()


def main():
    print("Initialize…")
    init = post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "example", "version": "1"}}})
    print(json.dumps(init, indent=2))

    print("\nTools list…")
    tools = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    print(json.dumps(tools, indent=2))

    root = os.environ.get("CLS_CODE_ROOT", str(Path.cwd()))
    print("\nCall search_code…")
    call = post({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "search_code", "arguments": {"query": "TODO|FIXME", "root": root, "maxResults": 10}},
    })
    print(json.dumps(call, indent=2))


if __name__ == "__main__":
    main()

