import sys
from pathlib import Path

import pytest


def require_fastapi():
    try:
        import fastapi  # noqa: F401
        from fastapi.testclient import TestClient  # noqa: F401
    except Exception as e:
        pytest.skip(f"fastapi not available: {e}")


def test_admin_ui_auth_and_render(tmp_path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ADMIN_TOKEN', 'adm')

    app = create_app()
    client = TestClient(app)

    r1 = client.get('/admin')
    assert r1.status_code == 401

    r2 = client.get('/admin', headers={'Authorization': 'Bearer adm'})
    assert r2.status_code == 200
    assert 'text/html' in r2.headers.get('content-type', '')
    assert 'Admin' in r2.text

