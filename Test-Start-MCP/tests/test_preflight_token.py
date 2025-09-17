import json
import os
import stat
import sys
import time
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


def _mk_app(tmp_path: Path):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app
    app = create_app()
    return TestClient(app)


def test_mcp_preflight_token_flow(tmp_path: Path, monkeypatch):
    """Enforcement on: check -> token -> run ok; missing token fails."""
    script = _make_script(tmp_path, """
print('ok')
import sys
sys.exit(0)
""")

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', str(script))
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')
    monkeypatch.setenv('TSM_REQUIRE_PREFLIGHT', '1')

    client = _mk_app(tmp_path)

    # Missing token should fail
    body = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "run_script",
            "arguments": {"path": str(script), "args": []}
        }
    }
    r = client.post('/mcp', json=body)
    assert r.status_code == 200
    resp = r.json()
    assert resp['result']['isError'] is True
    assert resp['result']['structuredContent']['error']['code'] == 'E_POLICY'

    # check_script to get token
    body = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {
            "name": "check_script",
            "arguments": {"path": str(script), "args": []}
        }
    }
    r = client.post('/mcp', json=body)
    assert r.status_code == 200
    token = r.json()['result']['structuredContent'].get('preflightToken')
    assert token

    # run_script with token succeeds
    body = {
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {
            "name": "run_script",
            "arguments": {"path": str(script), "args": [], "preflight_token": token}
        }
    }
    r = client.post('/mcp', json=body)
    assert r.status_code == 200
    resp = r.json()
    assert resp['result']['isError'] is False
    assert resp['result']['structuredContent']['exitCode'] == 0


def test_rest_preflight_token_missing_then_ok(tmp_path: Path, monkeypatch):
    script = _make_script(tmp_path, "print('hello')")
    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', str(script))
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--smoke')
    monkeypatch.setenv('TSM_REQUIRE_PREFLIGHT', '1')

    client = _mk_app(tmp_path)

    # Missing token -> 428
    r = client.post('/actions/run_script', json={"path": str(script), "args": []})
    assert r.status_code == 428

    # Get token via REST check_script
    r = client.post('/actions/check_script', json={"path": str(script), "args": []})
    assert r.status_code == 200
    token = r.json().get('preflightToken')
    assert token

    # Run with token -> 200
    r = client.post('/actions/run_script', json={"path": str(script), "args": [], "preflight_token": token})
    assert r.status_code == 200
    assert r.json().get('exitCode') == 0


def test_preflight_token_mismatch(tmp_path: Path, monkeypatch):
    script = _make_script(tmp_path, "print('x')")
    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', str(script))
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--smoke')
    monkeypatch.setenv('TSM_REQUIRE_PREFLIGHT', '1')

    client = _mk_app(tmp_path)

    # Get token for [] args
    r = client.post('/actions/check_script', json={"path": str(script), "args": []})
    token = r.json().get('preflightToken')
    assert token
    # Try to run with different args -> 428
    r = client.post('/actions/run_script', json={"path": str(script), "args": ["--smoke"], "preflight_token": token})
    assert r.status_code == 428
