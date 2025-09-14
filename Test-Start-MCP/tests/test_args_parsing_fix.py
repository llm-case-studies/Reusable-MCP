import os
import sys
from pathlib import Path

import pytest


def test_comma_separated_args_parsing(monkeypatch):
    """Test that comma-separated args are properly parsed"""
    # Add the server directory to the path
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from server.policy import list_allowed_scripts

    # Test with comma-separated args
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', '/test/script1.sh:/test/script2.sh')
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests,--kill-port,--smoke,--host,--port')

    scripts = list_allowed_scripts()

    assert len(scripts) == 2
    allowed_args = scripts[0]['allowedArgs']

    # Should have all individual args, not the comma-separated string
    expected_args = ['--host', '--kill-port', '--no-tests', '--port', '--smoke']
    assert allowed_args == expected_args

    # Should not have the comma-separated string as a single arg
    assert '--no-tests,--kill-port,--smoke,--host,--port' not in allowed_args


def test_mixed_separator_args_parsing(monkeypatch):
    """Test that mixed separators (colon and comma) work"""
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from server.policy import list_allowed_scripts

    # Test with mixed separators
    monkeypatch.setenv('TSM_ALLOWED_SCRIPTS', '/test/script.sh')
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests,--kill-port:--smoke;--host,--port')

    scripts = list_allowed_scripts()

    assert len(scripts) == 1
    allowed_args = scripts[0]['allowedArgs']

    # Should parse all args regardless of separator
    expected_args = ['--host', '--kill-port', '--no-tests', '--port', '--smoke']
    assert allowed_args == expected_args


def test_args_validation_with_comma_separated(monkeypatch):
    """Test that args validation works with comma-separated config"""
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from server.policy import _validate_args

    # Set comma-separated args
    monkeypatch.setenv('TSM_ALLOWED_ARGS', '--no-tests,--kill-port,--smoke,--host,--port')

    # Test valid args
    ok, err = _validate_args(['--no-tests', '--host', '127.0.0.1', '--port', '8080'])
    assert ok
    assert err is None

    # Test invalid arg
    ok, err = _validate_args(['--forbidden'])
    assert not ok
    assert err['code'] == 'E_BAD_ARG'
    assert 'not allowed' in err['message']