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


def _make_script(tmp_path: Path, lines: str, name: str) -> Path:
    p = tmp_path / name
    p.write_text("#!/usr/bin/env python3\n" + lines, encoding='utf-8')
    mode = p.stat().st_mode
    p.chmod(mode | stat.S_IXUSR)
    return p


def _auth_hdr(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_overlay_path_selector_clamps_only_matching(tmp_path: Path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    slow = _make_script(tmp_path, "import time\ntime.sleep(0.2)\nprint('slow')\n", 'slow.py')
    fast = _make_script(tmp_path, "print('fast')\n", 'fast.py')

    # Env
    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', f"{slow}:{fast}")
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--smoke')
    monkeypatch.setenv('TSM_ADMIN_TOKEN', 'adm')

    # Seed a tight profile
    state_fp = tmp_path / 'allowlist.json'
    seed = {
        'version': 1,
        'rules': [],
        'overlays': [],
        'profiles': {
            'tiny': {'caps': {'maxTimeoutMs': 50, 'maxBytes': 65536, 'maxStdoutLines': 200, 'concurrency': 1}, 'flagsAllowed': ['--smoke']}
        }
    }
    state_fp.write_text(json.dumps(seed), encoding='utf-8')
    monkeypatch.setenv('TSM_ALLOWED_FILE', str(state_fp))

    app = create_app()
    client = TestClient(app)

    # Assign PATH overlay for slow.py only
    r0 = client.post('/admin/session/profile', headers=_auth_hdr('adm'), json={'sessionId': 'sess-path', 'profile': 'tiny', 'ttlSec': 300, 'path': str(slow)})
    assert r0.status_code == 200 and r0.json().get('ok') is True

    # Preflight to record
    client.post('/actions/check_script', headers={'X-TSM-Session': 'sess-path'}, json={'path': str(slow), 'args': []})

    # Run slow with large timeout -> should time out due to clamp
    r1 = client.post('/actions/run_script', headers={'X-TSM-Session': 'sess-path'}, json={'path': str(slow), 'args': [], 'timeout_ms': 5000})
    assert r1.status_code == 200 and r1.json()['exitCode'] == -1

    # Run fast with same session and large timeout -> should NOT be clamped (no overlay match)
    r2 = client.post('/actions/run_script', headers={'X-TSM-Session': 'sess-path'}, json={'path': str(fast), 'args': [], 'timeout_ms': 5000})
    assert r2.status_code == 200 and r2.json()['exitCode'] in (0, 1)


def test_mcp_sessionId_argument_used_for_caps(tmp_path: Path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    slow = _make_script(tmp_path, "import time\ntime.sleep(0.2)\nprint('slow')\n", 'slow2.py')

    # Env
    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', str(slow))
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--smoke')
    monkeypatch.setenv('TSM_ADMIN_TOKEN', 'adm')
    # Preflight enforcement off for simplicity here
    monkeypatch.setenv('TSM_REQUIRE_PREFLIGHT', '0')

    # Profiles
    state_fp = tmp_path / 'allowlist.json'
    seed = {
        'version': 1,
        'rules': [],
        'overlays': [],
        'profiles': {
            'tiny': {'caps': {'maxTimeoutMs': 50, 'maxBytes': 65536, 'maxStdoutLines': 200, 'concurrency': 1}, 'flagsAllowed': ['--smoke']}
        }
    }
    state_fp.write_text(json.dumps(seed), encoding='utf-8')
    monkeypatch.setenv('TSM_ALLOWED_FILE', str(state_fp))

    app = create_app()
    client = TestClient(app)

    # Assign session-only overlay for sess-arg
    r0 = client.post('/admin/session/profile', headers=_auth_hdr('adm'), json={'sessionId': 'sess-arg', 'profile': 'tiny', 'ttlSec': 300})
    assert r0.status_code == 200 and r0.json().get('ok') is True

    # Call MCP run_script with sessionId in arguments; expect clamp -> timeout (-1)
    body = {
        "jsonrpc": "2.0",
        "id": 77,
        "method": "tools/call",
        "params": {
            "name": "run_script",
            "arguments": {"path": str(slow), "args": [], "timeout_ms": 5000, "sessionId": "sess-arg"}
        }
    }
    r1 = client.post('/mcp', json=body)
    assert r1.status_code == 200
    j1 = r1.json()['result']['structuredContent']
    assert j1['exitCode'] == -1

