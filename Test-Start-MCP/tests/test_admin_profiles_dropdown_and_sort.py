import json
import sys
from pathlib import Path

import pytest


def require_fastapi():
    try:
        import fastapi  # noqa: F401
        from fastapi.testclient import TestClient  # noqa: F401
    except Exception as e:
        pytest.skip(f"fastapi not available: {e}")


def test_admin_state_overlays_sorted_and_profiles_exposed(tmp_path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ADMIN_TOKEN', 'adm')

    # Seed state with profiles and two overlays out of order
    state_fp = tmp_path / 'allowlist.json'
    seed = {
        'version': 1,
        'rules': [],
        'overlays': [
            {'sessionId': 's1', 'profile': 'dev', 'expiresAt': '2099-01-01T00:00:00+00:00', 'id': 'o1', 'createdAt': '2020-01-01T00:00:00+00:00'},
            {'sessionId': 's2', 'profile': 'tester', 'expiresAt': '2099-01-02T00:00:00+00:00', 'id': 'o2', 'createdAt': '2021-01-01T00:00:00+00:00'}
        ],
        'profiles': {
            'tester': {'caps': {'maxTimeoutMs': 10000, 'maxBytes': 65536, 'maxStdoutLines': 200, 'concurrency': 1}, 'flagsAllowed': ['--smoke']},
            'dev': {'caps': {'maxTimeoutMs': 90000, 'maxBytes': 262144, 'maxStdoutLines': 1500, 'concurrency': 2}, 'flagsAllowed': ['--smoke']}
        }
    }
    state_fp.write_text(json.dumps(seed), encoding='utf-8')
    monkeypatch.setenv('TSM_ALLOWED_FILE', str(state_fp))

    app = create_app()
    client = TestClient(app)

    r = client.get('/admin/state', headers={'Authorization': 'Bearer adm'})
    assert r.status_code == 200
    j = r.json()
    # Sorted newest first (createdAt 2021 before 2020)
    ids = [o['id'] for o in j['overlays']]
    assert ids == ['o2', 'o1']
    # Profiles exposed
    assert set(j['profiles'].keys()) == {'tester', 'dev'}

