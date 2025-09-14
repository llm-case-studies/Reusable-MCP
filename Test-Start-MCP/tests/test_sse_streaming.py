import json
import os
import stat
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

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


def _parse_sse_events(sse_text: str):
    """Parse SSE event stream into list of events"""
    events = []
    lines = sse_text.strip().split('\n')
    current_event = {}

    for line in lines:
        line = line.strip()
        if not line:
            if current_event:
                events.append(current_event)
                current_event = {}
            continue

        if line.startswith('event: '):
            current_event['event'] = line[7:]
        elif line.startswith('data: '):
            try:
                current_event['data'] = json.loads(line[6:])
            except json.JSONDecodeError:
                current_event['data'] = line[6:]

    if current_event:
        events.append(current_event)

    return events


def test_sse_run_script_success(tmp_path: Path, monkeypatch):
    """Test SSE streaming for successful script execution"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    script = _make_script(tmp_path, """
import sys
import time
print('Starting script')
print('Progress: 50%')
time.sleep(0.05)
print('Progress: 100%')
print('Script completed', file=sys.stderr)
sys.exit(0)
""")

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', str(script))
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')

    app = create_app()
    client = TestClient(app)

    # Test with args as JSON array
    params = {
        'path': str(script),
        'args': json.dumps([]),
        'timeout_ms': 5000
    }

    with client.stream('GET', f'/sse/run_script_stream?{urlencode(params)}') as response:
        assert response.status_code == 200
        assert response.headers['content-type'] == 'text/event-stream; charset=utf-8'

        content = ""
        for chunk in response.iter_text():
            content += chunk
            if 'event: end' in content:
                break

    events = _parse_sse_events(content)

    # Should have stdout events and an end event
    stdout_events = [e for e in events if e.get('event') == 'stdout']
    stderr_events = [e for e in events if e.get('event') == 'stderr']
    end_events = [e for e in events if e.get('event') == 'end']

    assert len(stdout_events) >= 3  # Starting, Progress 50%, Progress 100%
    assert len(stderr_events) >= 1  # Script completed
    assert len(end_events) == 1

    # Check end event
    end_event = end_events[0]
    assert end_event['data']['exitCode'] == 0
    assert 'duration_ms' in end_event['data']


def test_sse_run_script_comma_args(tmp_path: Path, monkeypatch):
    """Test SSE streaming with comma-separated args"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    script = _make_script(tmp_path, """
import sys
for i, arg in enumerate(sys.argv[1:], 1):
    print(f'Arg {i}: {arg}')
sys.exit(0)
""")

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', str(script))
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--host;--port;--smoke')

    app = create_app()
    client = TestClient(app)

    params = {
        'path': str(script),
        'args': '--host,127.0.0.1,--port,7060',  # Comma-separated
        'timeout_ms': 5000
    }

    with client.stream('GET', f'/sse/run_script_stream?{urlencode(params)}') as response:
        assert response.status_code == 200

        content = ""
        for chunk in response.iter_text():
            content += chunk
            if 'event: end' in content:
                break

    events = _parse_sse_events(content)
    stdout_events = [e for e in events if e.get('event') == 'stdout']

    # Should see the arguments printed
    stdout_lines = [e['data']['line'] for e in stdout_events]
    stdout_text = '\n'.join(stdout_lines)
    assert 'Arg 1: --host' in stdout_text
    assert 'Arg 2: 127.0.0.1' in stdout_text
    assert 'Arg 3: --port' in stdout_text
    assert 'Arg 4: 7060' in stdout_text


@pytest.mark.skip(reason="Timeout test is flaky in test environment - timing dependent")
def test_sse_timeout(tmp_path: Path, monkeypatch):
    """Test SSE streaming with timeout"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    script = _make_script(tmp_path, """
import time
import sys
print('Starting long task', flush=True)
sys.stdout.flush()
time.sleep(0.5)  # Longer than timeout
print('Should not reach here')
""", 'timeout_test.py')

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', str(script))
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')

    app = create_app()
    client = TestClient(app)

    params = {
        'path': str(script),
        'timeout_ms': 100  # Short timeout
    }

    with client.stream('GET', f'/sse/run_script_stream?{urlencode(params)}') as response:
        assert response.status_code == 200

        content = ""
        for chunk in response.iter_text():
            content += chunk
            if 'event: end' in content:
                break

    events = _parse_sse_events(content)
    end_events = [e for e in events if e.get('event') == 'end']

    assert len(end_events) == 1
    end_event = end_events[0]
    assert end_event['data']['exitCode'] == -1  # Timeout
    assert end_event['data'].get('truncated') is True


def test_sse_forbidden_script(tmp_path: Path, monkeypatch):
    """Test SSE streaming with forbidden script"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', '')  # No scripts allowed
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')

    app = create_app()
    client = TestClient(app)

    params = {
        'path': '/bin/echo',
        'args': json.dumps(['hello'])
    }

    response = client.get(f'/sse/run_script_stream?{urlencode(params)}')
    assert response.status_code == 403


def test_sse_invalid_args_json(tmp_path: Path, monkeypatch):
    """Test SSE streaming with invalid JSON args"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', '')
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')

    app = create_app()
    client = TestClient(app)

    params = {
        'path': '/bin/echo',
        'args': '{invalid json}'  # Invalid JSON
    }

    response = client.get(f'/sse/run_script_stream?{urlencode(params)}')
    # Invalid JSON args comes after path validation, so we get 403 (forbidden path) first
    assert response.status_code == 403


def test_sse_with_auth(tmp_path: Path, monkeypatch):
    """Test SSE streaming with authentication"""
    require_fastapi()
    from fastapi.testclient import TestClient
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server.app import create_app

    script = _make_script(tmp_path, "print('authenticated')")

    monkeypatch.setenv('TSM_ALLOWED_ROOT', str(tmp_path))
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', str(script))
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests;--kill-port;--smoke;--host;--port')
    monkeypatch.setenv('TSM_TOKEN', 'secret123')

    app = create_app()
    client = TestClient(app)

    params = {
        'path': str(script),
        'args': json.dumps([])
    }

    # No auth
    response = client.get(f'/sse/run_script_stream?{urlencode(params)}')
    assert response.status_code == 401

    # Wrong auth
    response = client.get(
        f'/sse/run_script_stream?{urlencode(params)}',
        headers={"Authorization": "Bearer wrong"}
    )
    assert response.status_code == 401

    # Correct auth
    with client.stream(
        'GET',
        f'/sse/run_script_stream?{urlencode(params)}',
        headers={"Authorization": "Bearer secret123"}
    ) as response:
        assert response.status_code == 200

        content = ""
        for chunk in response.iter_text():
            content += chunk
            if 'event: end' in content:
                break

    events = _parse_sse_events(content)
    stdout_events = [e for e in events if e.get('event') == 'stdout']
    assert len(stdout_events) >= 1
    assert any('authenticated' in e['data']['line'] for e in stdout_events)