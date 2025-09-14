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


def test_health_and_list(tmp_path: Path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    # configure env policy
    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', '')
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port;--default-code-root;--logs-root;--home')

    app = create_app()
    client = TestClient(app)

    r = client.get('/healthz')
    assert r.status_code == 200
    assert r.json().get('ok') is True

    r = client.post('/actions/list_allowed', json={})
    assert r.status_code == 200
    assert 'scripts' in r.json()


def test_run_script_success_and_forbidden(tmp_path: Path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    script = _make_script(tmp_path, """
import sys
import time
print('hello')
print('warn', file=sys.stderr)
time.sleep(0.05)
print('done')
sys.exit(0)
""")

    # Policy allows only our script and root
    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', str(script))
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port;--default-code-root;--logs-root;--home')

    app = create_app()
    client = TestClient(app)

    r = client.post('/actions/run_script', json={'path': str(script), 'args': ['--smoke']})
    assert r.status_code == 200
    j = r.json()
    assert j['exitCode'] == 0
    assert 'hello' in j.get('stdout', '')
    assert 'warn' in j.get('stderr', '')

    # Forbidden root
    r2 = client.post('/actions/run_script', json={'path': '/bin/echo', 'args': []})
    assert r2.status_code in (400, 403)


def test_timeout_and_bad_flags(tmp_path: Path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    script = _make_script(tmp_path, """
import time
time.sleep(0.2)
print('late')
""", name='slow.py')
    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', str(script))
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port;--default-code-root;--logs-root;--home')

    app = create_app()
    client = TestClient(app)

    # short timeout
    r = client.post('/actions/run_script', json={'path': str(script), 'timeout_ms': 50})
    assert r.status_code == 200
    j = r.json()
    assert j['exitCode'] == -1  # timed out

    # bad positional arg
    r2 = client.post('/actions/run_script', json={'path': str(script), 'args': ['positional']})
    assert r2.status_code == 400
