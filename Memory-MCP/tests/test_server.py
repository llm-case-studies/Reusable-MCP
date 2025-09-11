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


def test_write_read_search(tmp_path: Path):
    require_fastapi()
    from fastapi.testclient import TestClient
    # import modules
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    home = tmp_path / 'memorydb'
    app = create_app(home)
    client = TestClient(app)

    # health
    r = client.get('/healthz')
    assert r.status_code == 200
    assert r.json().get('ok') is True

    # write
    payload = {
        'project': 'RoadNerd',
        'scope': 'project',
        'key': 'policy',
        'text': 'Dynamic tokens: max(512, n*120)',
        'tags': ['decision', 'prompt']
    }
    r = client.post('/actions/write_memory', json=payload)
    assert r.status_code == 200
    entry = r.json()
    assert entry['project'] == 'RoadNerd'
    assert entry['version'] == 1

    # read latest by key
    r = client.post('/actions/read_memory', json={'project': 'RoadNerd', 'key': 'policy'})
    assert r.status_code == 200
    entry2 = r.json()['entry']
    assert entry2['text'].startswith('Dynamic tokens')

    # search
    r = client.post('/actions/search_memory', json={'query': 'tokens', 'project': 'RoadNerd', 'k': 5})
    assert r.status_code == 200
    items = r.json()['items']
    assert len(items) >= 1

    # list
    r = client.post('/actions/list_memories', json={'project': 'RoadNerd'})
    assert r.status_code == 200
    assert len(r.json()['items']) >= 1

