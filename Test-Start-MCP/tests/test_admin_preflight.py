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


def _make_script(tmp_path: Path, lines: str = "print('ok')", name: str = 'script.py') -> Path:
    p = tmp_path / name
    p.write_text("#!/usr/bin/env python3\n" + lines, encoding='utf-8')
    mode = p.stat().st_mode
    p.chmod(mode | stat.S_IXUSR)
    return p


def _auth_hdr(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_admin_state_auth_and_seed(tmp_path: Path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    # Env
    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    state_fp = tmp_path / 'allowlist.json'
    seed = {
        'version': 1,
        'rules': [],
        'overlays': [],
        'profiles': {
            'tester': {'caps': {'maxTimeoutMs': 5000, 'maxBytes': 65536, 'maxStdoutLines': 200, 'concurrency': 1}, 'flagsAllowed': ['--smoke']}
        }
    }
    state_fp.write_text(json.dumps(seed), encoding='utf-8')
    monkeypatch.setenv('TSM_ALLOWED_FILE', str(state_fp))
    monkeypatch.setenv('TSM_ADMIN_TOKEN', 'adm')

    app = create_app()
    client = TestClient(app)

    # Unauthorized
    r = client.get('/admin/state')
    assert r.status_code == 401

    # Authorized
    r = client.get('/admin/state', headers=_auth_hdr('adm'))
    assert r.status_code == 200
    j = r.json()
    assert j['version'] == 1
    assert 'profiles' in j and 'tester' in j['profiles']


def test_admin_add_and_remove_path_rule(tmp_path: Path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    script = _make_script(tmp_path, "print('hello')", 'run.sh')

    # Env
    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    state_fp = tmp_path / 'allowlist.json'
    state_fp.write_text(json.dumps({'version': 1, 'rules': [], 'overlays': [], 'profiles': {}}), encoding='utf-8')
    monkeypatch.setenv('TSM_ALLOWED_FILE', str(state_fp))
    monkeypatch.setenv('TSM_ADMIN_TOKEN', 'adm')

    app = create_app()
    client = TestClient(app)

    # Add rule (path)
    body = {
        'type': 'path',
        'path': str(script),
        'flagsAllowed': ['--smoke'],
        'ttlSec': 60
    }
    r = client.post('/admin/allowlist/add', headers=_auth_hdr('adm'), json=body)
    assert r.status_code == 200
    j = r.json()
    assert j['ok'] is True
    rid = j['rule']['id']
    assert j['rule']['type'] == 'path'

    # State should show the rule
    r2 = client.get('/admin/state', headers=_auth_hdr('adm'))
    j2 = r2.json()
    assert any(r['id'] == rid for r in j2['rules'])

    # Remove rule
    r3 = client.post('/admin/allowlist/remove', headers=_auth_hdr('adm'), json={'id': rid})
    assert r3.status_code == 200
    assert r3.json()['ok'] is True

    # State should be empty rules
    r4 = client.get('/admin/state', headers=_auth_hdr('adm'))
    j4 = r4.json()
    assert all(r['id'] != rid for r in j4['rules'])


def test_actions_check_script_preflight_with_rule(tmp_path: Path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    script = _make_script(tmp_path, "print('ok')", 'probe.py')

    # Env
    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    # Global allowed flags include --smoke but not --forbidden
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--smoke;--no-tests')
    state_fp = tmp_path / 'allowlist.json'
    state_fp.write_text(json.dumps({'version': 1, 'rules': [], 'overlays': [], 'profiles': {}}), encoding='utf-8')
    monkeypatch.setenv('TSM_ALLOWED_FILE', str(state_fp))

    app = create_app()
    client = TestClient(app)

    # Initially, with no rule, allowed by global flags and boundary
    r0 = client.post('/actions/check_script', json={'path': str(script), 'args': ['--smoke']})
    assert r0.status_code == 200
    j0 = r0.json()
    assert j0['allowed'] is True
    assert j0['matchedRule'] is None

    # Add a rule narrowing flags to --smoke only
    monkeypatch.setenv('TSM_ADMIN_TOKEN', 'adm')
    app = create_app()  # re-create app to pick up token for admin endpoints
    client = TestClient(app)
    r1 = client.post('/admin/allowlist/add', headers=_auth_hdr('adm'), json={'type': 'path', 'path': str(script), 'flagsAllowed': ['--smoke']})
    assert r1.status_code == 200
    # Now preflight with allowed flag
    r2 = client.post('/actions/check_script', json={'path': str(script), 'args': ['--smoke']})
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2['allowed'] is True
    assert j2['matchedRule'] is not None

    # Preflight with disallowed flag should be rejected
    r3 = client.post('/actions/check_script', json={'path': str(script), 'args': ['--forbidden']})
    assert r3.status_code == 200
    j3 = r3.json()
    assert j3['allowed'] is False
    assert any(str(x).startswith('disallowed_flags') for x in j3['reasons'])


def test_preflight_enforcement_for_run_script(tmp_path: Path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    # Make script
    script = _make_script(tmp_path, "print('ok')", 'probe.py')

    # Env policy
    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', str(script))
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--smoke')
    # Enforce preflight
    monkeypatch.setenv('TSM_REQUIRE_PREFLIGHT', '1')

    # Seed policy file
    state_fp = tmp_path / 'allowlist.json'
    state_fp.write_text(json.dumps({'version': 1, 'rules': [], 'overlays': [], 'profiles': {}}), encoding='utf-8')
    monkeypatch.setenv('TSM_ALLOWED_FILE', str(state_fp))

    app = create_app()
    client = TestClient(app)

    # Attempt run_script without preflight should fail (requires session id header too)
    r0 = client.post('/actions/run_script', json={'path': str(script), 'args': ['--smoke']})
    assert r0.status_code == 428
    assert r0.json().get('error') == 'E_POLICY'

    # With session but no preflight still fails
    r1 = client.post('/actions/run_script', headers={'X-TSM-Session': 'sess-1'}, json={'path': str(script), 'args': ['--smoke']})
    assert r1.status_code == 428
    assert r1.json().get('error') == 'E_POLICY'

    # Do preflight
    r2 = client.post('/actions/check_script', headers={'X-TSM-Session': 'sess-1'}, json={'path': str(script), 'args': ['--smoke']})
    assert r2.status_code == 200
    assert r2.json()['allowed'] is True

    # Now run_script succeeds
    r3 = client.post('/actions/run_script', headers={'X-TSM-Session': 'sess-1'}, json={'path': str(script), 'args': ['--smoke']})
    assert r3.status_code == 200
    assert r3.json().get('exitCode') == 0


def test_overlay_profile_caps_clamps_timeout(tmp_path: Path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    # Create a slow script (~200ms)
    slow = _make_script(tmp_path, """
import time, sys
time.sleep(0.2)
print('slow done')
sys.exit(0)
""", 'slow.py')

    # Env baseline
    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', str(slow))
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--smoke')
    monkeypatch.setenv('TSM_ADMIN_TOKEN', 'adm')
    # Enforce preflight
    monkeypatch.setenv('TSM_REQUIRE_PREFLIGHT', '1')

    # Seed profiles with a very small timeout
    state_fp = tmp_path / 'allowlist.json'
    seed = {
        'version': 1,
        'rules': [],
        'overlays': [],
        'profiles': {
            'tiny': {
                'caps': {'maxTimeoutMs': 50, 'maxBytes': 65536, 'maxStdoutLines': 200, 'concurrency': 1},
                'flagsAllowed': ['--smoke']
            }
        }
    }
    state_fp.write_text(json.dumps(seed), encoding='utf-8')
    monkeypatch.setenv('TSM_ALLOWED_FILE', str(state_fp))

    app = create_app()
    client = TestClient(app)

    # Assign overlay profile to session
    r0 = client.post('/admin/session/profile', headers=_auth_hdr('adm'), json={'sessionId': 'sess-2', 'profile': 'tiny', 'ttlSec': 60})
    assert r0.status_code == 200 and r0.json().get('ok') is True

    # Do preflight to record permission
    r1 = client.post('/actions/check_script', headers={'X-TSM-Session': 'sess-2'}, json={'path': str(slow), 'args': []})
    assert r1.status_code == 200 and r1.json()['allowed'] is True

    # Run with a large requested timeout; should be clamped to 50ms and time out
    r2 = client.post('/actions/run_script', headers={'X-TSM-Session': 'sess-2'}, json={'path': str(slow), 'args': [], 'timeout_ms': 5000})
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2['exitCode'] == -1  # timeout due to clamp
