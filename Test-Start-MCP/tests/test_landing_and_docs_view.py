import sys
from pathlib import Path

import pytest


def require_fastapi():
    try:
        import fastapi  # noqa: F401
        from fastapi.testclient import TestClient  # noqa: F401
    except Exception as e:
        pytest.skip(f"fastapi not available: {e}")


def test_landing_and_docs_view(tmp_path, monkeypatch):
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    # Ensure allowed root so app starts
    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))

    app = create_app()
    client = TestClient(app)

    r = client.get('/')
    assert r.status_code == 200
    assert 'Test‑Start‑MCP' in r.text or 'Test-Start-MCP' in r.text

    # README is expected to exist and contain project name
    r2 = client.get('/docs/view', params={'name': 'readme'})
    assert r2.status_code == 200
    assert 'Test-Start-MCP' in r2.text or 'Test‑Start‑MCP' in r2.text
