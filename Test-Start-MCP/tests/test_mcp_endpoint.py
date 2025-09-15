import json
import os
import stat
import sys
from pathlib import Path

import pytest


def require_fastapi():
    try:
        import fastapi  # noqa: F401
        from fastapi.testclient import TestClient  # noqa: F401
    except Exception as e:
        pytest.skip(f"fastapi not available: {e}")


def _make_script(tmp_path: Path, lines: str, name: str = 'script.py') -> Path:
    p = tmp_path / name
    p.write_text("#!/usr/bin/env python3\n" + lines, encoding='utf-8')
    mode = p.stat().st_mode
    p.chmod(mode | stat.S_IXUSR)
    return p


def test_mcp_initialize(tmp_path: Path, monkeypatch):
    """Test MCP initialize endpoint"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', '')
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')

    app = create_app()
    client = TestClient(app)

    # Test initialize
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"}
        }
    }
    r = client.post('/mcp', json=body)
    assert r.status_code == 200
    resp = r.json()
    assert resp['jsonrpc'] == '2.0'
    assert resp['id'] == 1
    assert 'result' in resp
    assert resp['result']['protocolVersion'] == '2025-06-18'
    assert 'capabilities' in resp['result']
    assert resp['result']['serverInfo']['name'] == 'Test-Start-MCP'


def test_mcp_tools_list(tmp_path: Path, monkeypatch):
    """Test MCP tools/list endpoint"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', '')
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')

    app = create_app()
    client = TestClient(app)

    body = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    r = client.post('/mcp', json=body)
    assert r.status_code == 200
    resp = r.json()
    assert resp['jsonrpc'] == '2.0'
    assert resp['id'] == 2
    assert 'result' in resp
    assert 'tools' in resp['result']
    tools = resp['result']['tools']
    # At least the two core tools must be present; optional extras (e.g., check_script) may be added.
    assert len(tools) >= 2
    tool_names = {t['name'] for t in tools}
    assert 'run_script' in tool_names
    assert 'list_allowed' in tool_names
    # If check_script is present, it should have expected fields
    if 'check_script' in tool_names:
        chk = next(t for t in tools if t['name'] == 'check_script')
        assert 'inputSchema' in chk and 'outputSchema' in chk


def test_mcp_run_script_success(tmp_path: Path, monkeypatch):
    """Test MCP tools/call run_script success"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    script = _make_script(tmp_path, """
print('mcp test output')
import sys
sys.exit(0)
""")

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', str(script))
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')

    app = create_app()
    client = TestClient(app)

    body = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "run_script",
            "arguments": {
                "path": str(script),
                "args": [],
                "timeout_ms": 5000
            }
        }
    }
    r = client.post('/mcp', json=body)
    assert r.status_code == 200
    resp = r.json()
    assert resp['jsonrpc'] == '2.0'
    assert resp['id'] == 3
    assert 'result' in resp
    result = resp['result']
    assert 'content' in result
    assert 'structuredContent' in result
    assert result['isError'] is False
    assert result['structuredContent']['exitCode'] == 0
    assert 'mcp test output' in result['structuredContent']['stdout']


def test_mcp_run_script_error(tmp_path: Path, monkeypatch):
    """Test MCP tools/call run_script with invalid path"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', '')
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')

    app = create_app()
    client = TestClient(app)

    body = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "run_script",
            "arguments": {
                "path": "/invalid/path",
                "args": []
            }
        }
    }
    r = client.post('/mcp', json=body)
    assert r.status_code == 200
    resp = r.json()
    assert resp['jsonrpc'] == '2.0'
    assert resp['id'] == 4
    assert 'result' in resp
    result = resp['result']
    assert result['isError'] is True
    assert 'error' in result['structuredContent']


def test_mcp_list_allowed(tmp_path: Path, monkeypatch):
    """Test MCP tools/call list_allowed"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    script1 = _make_script(tmp_path, "print('script1')", 'script1.py')
    script2 = _make_script(tmp_path, "print('script2')", 'script2.py')

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', f'{script1}:{script2}')
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')

    app = create_app()
    client = TestClient(app)

    body = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "list_allowed",
            "arguments": {}
        }
    }
    r = client.post('/mcp', json=body)
    assert r.status_code == 200
    resp = r.json()
    assert resp['jsonrpc'] == '2.0'
    assert resp['id'] == 5
    assert 'result' in resp
    result = resp['result']
    assert 'structuredContent' in result
    scripts = result['structuredContent']['scripts']
    assert len(scripts) == 2
    paths = {s['path'] for s in scripts}
    assert str(script1) in paths
    assert str(script2) in paths


def test_mcp_unknown_method(tmp_path: Path, monkeypatch):
    """Test MCP unknown method"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', '')
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')

    app = create_app()
    client = TestClient(app)

    body = {"jsonrpc": "2.0", "id": 6, "method": "unknown/method"}
    r = client.post('/mcp', json=body)
    assert r.status_code == 200
    resp = r.json()
    assert resp['jsonrpc'] == '2.0'
    assert resp['id'] == 6
    assert 'error' in resp
    assert resp['error']['code'] == -32601


def test_mcp_batch_request(tmp_path: Path, monkeypatch):
    """Test MCP batch requests"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', '')
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')

    app = create_app()
    client = TestClient(app)

    # Batch request with initialize and tools/list
    body = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    ]
    r = client.post('/mcp', json=body)
    assert r.status_code == 200
    resp = r.json()
    assert isinstance(resp, list)
    assert len(resp) == 2
    assert resp[0]['id'] == 1
    assert resp[1]['id'] == 2


def test_mcp_auth_required(tmp_path: Path, monkeypatch):
    """Test MCP with auth token required"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', '')
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')
    monkeypatch.setenv('TSM_TOKEN', 'test-secret')

    app = create_app()
    client = TestClient(app)

    # No auth header
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    r = client.post('/mcp', json=body)
    assert r.status_code == 401

    # Wrong auth
    r = client.post('/mcp', json=body, headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401

    # Correct auth
    r = client.post('/mcp', json=body, headers={"Authorization": "Bearer test-secret"})
    assert r.status_code == 200
