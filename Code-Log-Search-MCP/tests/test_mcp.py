import sys
from pathlib import Path

import pytest


def require_fastapi():
    try:
        import fastapi  # noqa: F401
        from fastapi.testclient import TestClient  # noqa: F401
    except Exception as e:
        pytest.skip(f"fastapi not available: {e}")


def test_mcp_initialize_and_tools(tmp_path: Path):
    require_fastapi()
    from fastapi.testclient import TestClient

    # Import
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    code_root = tmp_path / 'proj'
    code_root.mkdir()
    (code_root / 'a.txt').write_text('hello\nnum_predict = 42\n')

    logs_root = tmp_path / 'logs'
    logs_root.mkdir()
    (logs_root / '20250101.jsonl').write_text('{"mode":"brainstorm","msg":"ok"}\n')

    app = create_app(code_root, logs_root)
    client = TestClient(app)

    init = client.post('/mcp', json={
        'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
        'params': {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 't', 'version': '1'}}
    })
    assert init.status_code == 200
    assert init.json().get('result', {}).get('protocolVersion') == '2025-06-18'

    tools = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
    assert tools.status_code == 200
    names = [t['name'] for t in tools.json()['result']['tools']]
    assert 'search_code' in names and 'search_logs' in names

    call = client.post('/mcp', json={
        'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
        'params': {'name': 'search_code', 'arguments': {'query': 'num_predict', 'root': str(code_root)}}
    })
    assert call.status_code == 200
    res = call.json()['result']['structuredContent']
    assert isinstance(res.get('hits'), list)

    call2 = client.post('/mcp', json={
        'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call',
        'params': {'name': 'search_logs', 'arguments': {'query': 'brainstorm', 'date': '20250101', 'mode': 'brainstorm', 'maxResults': 5}}
    })
    assert call2.status_code == 200
    res2 = call2.json()['result']['structuredContent']
    assert isinstance(res2.get('entries'), list) and len(res2['entries']) == 1


def test_mcp_literal_and_forbidden_root(tmp_path: Path):
    require_fastapi()
    from fastapi.testclient import TestClient

    # Import
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    code_root = tmp_path / 'proj'
    code_root.mkdir()
    (code_root / 'a.txt').write_text('hello\nnum_predict = 42\n')
    logs_root = tmp_path / 'logs'
    logs_root.mkdir()

    app = create_app(code_root, logs_root)
    client = TestClient(app)

    # literal mode search
    call = client.post('/mcp', json={
        'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
        'params': {'name': 'search_code', 'arguments': {'query': 'num_predict', 'root': str(code_root), 'literal': True}}
    })
    assert call.status_code == 200
    sc = call.json()['result']['structuredContent']
    assert isinstance(sc.get('hits'), list) and len(sc['hits']) >= 1

    # forbidden root (outside default_code_root)
    call2 = client.post('/mcp', json={
        'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call',
        'params': {'name': 'search_code', 'arguments': {'query': 'x', 'root': '/'}}
    })
    assert call2.status_code == 200
    res = call2.json()['result']
    assert res.get('isError') is True
    assert res.get('structuredContent', {}).get('error', {}).get('message') == 'forbidden_root'


def test_rest_forbidden_root(tmp_path: Path):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    code_root = tmp_path / 'proj'
    code_root.mkdir()
    app = create_app(code_root, tmp_path / 'logs')
    client = TestClient(app)

    r = client.post('/actions/search_code', json={'query': 'x', 'root': '/'})
    assert r.status_code == 400
    assert r.json().get('error') == 'forbidden_root'
