#!/usr/bin/env python3
import json
import os
import sys
from typing import Any, Dict

import requests


BASE = os.environ.get("MEM_URL", "http://127.0.0.1:7090/mcp")
TOKEN = os.environ.get("MEM_TOKEN", "")


def post(payload: Dict[str, Any]):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    r = requests.post(BASE, headers=headers, data=json.dumps(payload))
    r.raise_for_status()
    return r.json()


def main():
    print("Initialize…")
    init = post({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "example", "version": "1"}},
    })
    print(json.dumps(init, indent=2))

    print("\nTools list…")
    tools = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    print(json.dumps(tools, indent=2))

    print("\nCall write_memory…")
    call = post({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "write_memory",
            "arguments": {"project": "RoadNerd", "scope": "project", "key": "policy", "text": "From examples/mcp_client.py", "tags": ["example"]},
        },
    })
    print(json.dumps(call, indent=2))


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        print("HTTP error:", e, file=sys.stderr)
        if e.response is not None:
            print(e.response.text, file=sys.stderr)
        sys.exit(2)

