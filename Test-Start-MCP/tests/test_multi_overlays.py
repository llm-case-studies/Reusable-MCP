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


def test_multi_overlays_selection_and_remove(tmp_path: Path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    proj = tmp_path / 'proj'
    proj.mkdir()
    subA = proj / 'A'
    subA.mkdir()
    subB = proj / 'B'
    subB.mkdir()

    slowA = _make_script(subA, "import time\ntime.sleep(0.15)\nprint('A')\n", 'run.py')
    slowB = _make_script(subB, "import time\ntime.sleep(0.15)\nprint('B')\n", 'run.py')

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', f"{slowA}:{slowB}")
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--smoke')
    monkeypatch.setenv('TSM_ADMIN_TOKEN', 'adm')
    # Preflight enforcement off for simplicity
    monkeypatch.setenv('TSM_REQUIRE_PREFLIGHT', '0')

    # Profiles: tiny vs large
    state_fp = tmp_path / 'allowlist.json'
    seed = {
        'version': 1,
        'rules': [],
        'overlays': [],
        'profiles': {
            'tiny': {'caps': {'maxTimeoutMs': 50, 'maxBytes': 65536, 'maxStdoutLines': 200, 'concurrency': 1}, 'flagsAllowed': ['--smoke']},
            'large': {'caps': {'maxTimeoutMs': 5000, 'maxBytes': 262144, 'maxStdoutLines': 1500, 'concurrency': 2}, 'flagsAllowed': ['--smoke']}
        }
    }
    state_fp.write_text(json.dumps(seed), encoding='utf-8')
    monkeypatch.setenv('TSM_ALLOWED_FILE', str(state_fp))

    app = create_app()
    client = TestClient(app)

    # Assign two overlays for same session: session-only large (fallback) and scope A tiny (restrictive)
    r0 = client.post('/admin/session/profile', headers=_auth_hdr('adm'), json={'sessionId': 'sess-multi', 'profile': 'large', 'ttlSec': 300})
    assert r0.status_code == 200 and r0.json().get('ok') is True
    r1 = client.post('/admin/session/profile', headers=_auth_hdr('adm'), json={'sessionId': 'sess-multi', 'profile': 'tiny', 'ttlSec': 300, 'scopeRoot': str(subA), 'patterns': ['**']})
    assert r1.status_code == 200 and r1.json().get('ok') is True

    # Run in A -> should timeout due to tiny
    jA = client.post('/actions/run_script', headers={'X-TSM-Session': 'sess-multi'}, json={'path': str(slowA), 'args': [], 'timeout_ms': 5000}).json()
    assert jA['exitCode'] == -1
    # Run in B -> should pass due to large fallback
    jB = client.post('/actions/run_script', headers={'X-TSM-Session': 'sess-multi'}, json={'path': str(slowB), 'args': [], 'timeout_ms': 5000}).json()
    assert jB['exitCode'] == 0

    # Remove the scope overlay; ensure fallback applies to A as well now (no timeout)
    st = client.get('/admin/state', headers=_auth_hdr('adm')).json()
    # Find an overlay with scopeRoot=subA
    oid = None
    for o in st.get('overlays', []):
        if o.get('scopeRoot') == str(subA):
            oid = o.get('id')
            break
    assert oid
    rrm = client.post('/admin/overlay/remove', headers=_auth_hdr('adm'), json={'id': oid})
    assert rrm.status_code == 200 and rrm.json().get('ok') is True

    jA2 = client.post('/actions/run_script', headers={'X-TSM-Session': 'sess-multi'}, json={'path': str(slowA), 'args': [], 'timeout_ms': 5000}).json()
    assert jA2['exitCode'] == 0

