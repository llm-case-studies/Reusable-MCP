import sys
from pathlib import Path

import pytest


def require_fastapi():
    try:
        import fastapi  # noqa: F401
        from fastapi.testclient import TestClient  # noqa: F401
    except Exception as e:
        pytest.skip(f"fastapi not available: {e}")


def write_jsonl(path: Path, rows):
    import json
    with path.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def test_mcp_flow(tmp_path: Path):
    require_fastapi()
    from fastapi.testclient import TestClient

    # Import modules
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from indexer.build_index import index_transcripts
    from server.app import create_app

    # Prepare transcripts and index
    home = tmp_path / 'chatdb'
    tdir = home / 'transcripts'
    tdir.mkdir(parents=True, exist_ok=True)
    rows = [
        {'chat_id': 's1', 'project': 'RoadNerd', 'ts': '2025-09-11T10:00:00', 'role': 'assistant', 'text': 'tokens brainstorm'},
        {'chat_id': 's1', 'project': 'RoadNerd', 'ts': '2025-09-11T10:05:00', 'role': 'user', 'text': 'more text'},
    ]
    write_jsonl(tdir / 'RoadNerd.jsonl', rows)
    index_transcripts(home)

    app = create_app(home)
    client = TestClient(app)

    init = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 't', 'version': '1'}}})
    assert init.status_code == 200
    assert init.json()['result']['protocolVersion'] == '2025-06-18'

    tools = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
    assert tools.status_code == 200
    names = [t['name'] for t in tools.json()['result']['tools']]
    assert 'search_previous_chats' in names

    call = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'search_previous_chats', 'arguments': {'query': 'tokens', 'project': 'RoadNerd', 'k': 5}}})
    assert call.status_code == 200
    items = call.json()['result']['structuredContent']['items']
    assert isinstance(items, list) and len(items) >= 1

