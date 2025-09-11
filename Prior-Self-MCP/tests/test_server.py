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


def write_jsonl(path: Path, rows):
    with path.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def test_endpoints_basic(tmp_path: Path):
    require_fastapi()

    # Import after fastapi check
    from fastapi.testclient import TestClient
    # Make modules importable
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from indexer.build_index import index_transcripts
    from server.app import create_app

    # Prepare home with transcripts
    home = tmp_path / 'chatdb'
    tdir = home / 'transcripts'
    tdir.mkdir(parents=True, exist_ok=True)

    rows = [
        {
            'chat_id': 'session_1', 'project': 'RoadNerd', 'ts': '2025-09-11T10:00:00',
            'role': 'assistant', 'text': 'Dynamic tokens set to max(512, n*120) for brainstorm'
        },
        {
            'chat_id': 'session_1', 'project': 'RoadNerd', 'ts': '2025-09-11T10:05:00',
            'role': 'user', 'text': 'Parsing failed with numbered list'
        },
        {
            'chat_id': 'session_2', 'project': 'RoadNerd', 'ts': '2025-09-11T11:00:00',
            'role': 'assistant', 'text': 'Expanded categories to cover boot/power/hardware'
        },
    ]
    write_jsonl(tdir / 'RoadNerd.jsonl', rows)

    # Build index
    index_transcripts(home)

    # Create app and client
    app = create_app(home)
    client = TestClient(app)

    # Health
    r = client.get('/healthz')
    assert r.status_code == 200
    assert r.json().get('ok') is True

    # Search previous chats
    r = client.post('/actions/search_previous_chats', json={'query': 'tokens', 'project': 'RoadNerd'})
    assert r.status_code == 200
    items = r.json().get('items', [])
    assert any('tokens' in (it.get('excerpt') or '') for it in items)

    # Get context
    r = client.post('/actions/get_chat_context', json={'chat_id': 'session_1'})
    assert r.status_code == 200
    msgs = r.json().get('messages', [])
    assert len(msgs) == 2
    assert msgs[0]['role'] == 'assistant'

    # List sessions
    r = client.post('/actions/list_sessions', json={'project': 'RoadNerd'})
    assert r.status_code == 200
    sessions = r.json().get('sessions', [])
    assert any(s['chat_id'] == 'session_1' for s in sessions)

    # Summarize decisions (stub)
    r = client.post('/actions/summarize_decisions', json={'chat_id': 'session_1'})
    assert r.status_code == 200
    assert 'decisions' in r.json()

