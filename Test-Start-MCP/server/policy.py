import json
import logging
import os
import shlex
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PROTOCOL_VERSION = '2025-06-18'


def _split_env_list(val: Optional[str]) -> List[str]:
    if not val:
        return []
    # Support colon or semicolon separated
    items = []
    for part in val.replace(';', ':').split(':'):
        s = part.strip()
        if s:
            items.append(s)
    return items


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None:
        return default
    try:
        return int(str(v).strip())
    except Exception:
        return default


def auth_ok(request) -> bool:
    token = os.environ.get('TSM_TOKEN')
    if not token:
        return True
    hdr = request.headers.get('Authorization')
    if not hdr or not hdr.startswith('Bearer '):
        return False
    return hdr.split(' ', 1)[1].strip() == token.strip()


def list_allowed_scripts() -> List[Dict[str, Any]]:
    allowed = _split_env_list(os.environ.get('TSM_ALLOWED_SCRIPTS'))
    allowed_args = set(_split_env_list(os.environ.get('TSM_ALLOWED_ARGS')))
    out = []
    for p in allowed:
        out.append({'path': p, 'allowedArgs': sorted(list(allowed_args))})
    return out


def _is_under_root(p: Path, root: Path) -> bool:
    try:
        p_r = p.resolve()
        r_r = root.resolve()
        return r_r in p_r.parents or p_r == r_r
    except Exception:
        return False


def _filter_env(user_env: Dict[str, str]) -> Dict[str, str]:
    allow = set(_split_env_list(os.environ.get('TSM_ENV_ALLOWLIST')))
    out: Dict[str, str] = {}
    # First prefer explicit provided values
    for k, v in (user_env or {}).items():
        if k in allow and isinstance(v, str):
            out[k] = v
    # Then fall back to process env for allowed keys
    for k in allow:
        if k not in out and k in os.environ:
            out[k] = os.environ[k]
    return out


def _normalize_args(raw_args: Iterable[Any]) -> List[str]:
    out: List[str] = []
    for a in (raw_args or []):
        if a is None:
            continue
        s = str(a)
        out.append(s)
    return out


def _validate_args(args: List[str]) -> Tuple[bool, Optional[Dict[str, str]]]:
    allowed = set(_split_env_list(os.environ.get('TSM_ALLOWED_ARGS')))
    i = 0
    while i < len(args):
        tok = args[i]
        if tok.startswith('--'):
            if tok not in allowed:
                return False, {'code': 'E_BAD_ARG', 'message': f'flag not allowed: {tok}'}
            # Flags expecting a value
            if tok in ('--host', '--port', '--default-code-root', '--logs-root', '--home'):
                if i + 1 >= len(args):
                    return False, {'code': 'E_BAD_ARG', 'message': f'missing value for {tok}'}
                val = args[i + 1]
                if tok == '--port':
                    if not str(val).isdigit():
                        return False, {'code': 'E_BAD_ARG', 'message': 'port must be integer'}
                i += 2
                continue
            # Standalone boolean flags
            i += 1
            continue
        else:
            # Disallow positional args unless after a "--" separator
            if tok == '--':
                i += 1
                continue
            return False, {'code': 'E_BAD_ARG', 'message': f'positional not allowed: {tok}'}
    return True, None


@dataclass
class Prepared:
    path: Path
    argv: List[str]
    cwd: Path
    env: Dict[str, str]
    timeout_ms: int
    max_output_bytes: int
    max_line_bytes: int
    log_dir: Optional[Path]


def validate_and_prepare(path: str, args: Iterable[Any], env: Optional[Dict[str, str]], timeout_ms: Optional[int]) -> Tuple[bool, Optional[Dict[str, str]], Optional[Prepared]]:
    # Validate allowed root
    allowed_root_str = os.environ.get('TSM_ALLOWED_ROOT')
    if not allowed_root_str:
        return False, {'code': 'E_POLICY', 'message': 'TSM_ALLOWED_ROOT not set'}, None
    allowed_root = Path(allowed_root_str)

    try:
        spath = Path(path)
    except Exception:
        return False, {'code': 'E_BAD_ARG', 'message': 'invalid path'}, None
    if not _is_under_root(spath, allowed_root):
        return False, {'code': 'E_FORBIDDEN', 'message': 'path not under allowed root'}, None

    if not spath.exists() or not spath.is_file():
        return False, {'code': 'E_BAD_ARG', 'message': 'path does not exist'}, None

    # Check allowlist of scripts
    allowed_scripts = set(_split_env_list(os.environ.get('TSM_ALLOWED_SCRIPTS')))
    if str(spath) not in allowed_scripts:
        return False, {'code': 'E_FORBIDDEN', 'message': 'script not in allowlist'}, None

    # Args
    norm_args = _normalize_args(args)
    ok, err = _validate_args(norm_args)
    if not ok:
        return False, err, None

    # Build argv; do not use shell
    argv = [str(spath)] + norm_args

    # Timeout and limits
    tout = int(timeout_ms) if timeout_ms is not None else _env_int('TSM_TIMEOUT_MS_DEFAULT', 90_000)
    max_output = _env_int('TSM_MAX_OUTPUT_BYTES', 262_144)
    max_line = _env_int('TSM_MAX_LINE_BYTES', 8192)
    log_dir_env = os.environ.get('TSM_LOG_DIR', 'Test-Start-MCP/logs')
    log_dir = Path(log_dir_env) if log_dir_env else None

    # Env filtering
    run_env = os.environ.copy()
    run_env.update(_filter_env(env or {}))

    return True, None, Prepared(
        path=spath,
        argv=argv,
        cwd=spath.parent,
        env=run_env,
        timeout_ms=tout,
        max_output_bytes=max_output,
        max_line_bytes=max_line,
        log_dir=log_dir,
    )


def _truncate_text(s: str, limit: int) -> Tuple[str, bool]:
    if len(s.encode('utf-8')) <= limit:
        return s, False
    # Truncate by characters but keep within byte budget approximately
    enc = s.encode('utf-8')[: max(0, limit - 3)]
    try:
        out = enc.decode('utf-8', errors='ignore') + '…'
    except Exception:
        out = s[: max(0, limit // 2)] + '…'
    return out, True


def _audit_log(prep: Prepared, result: Dict[str, Any]) -> None:
    try:
        if not prep.log_dir:
            return
        prep.log_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime('%Y%m%d')
        fp = prep.log_dir / f'exec-{ts}.jsonl'
        line = {
            'ts': int(time.time() * 1000),
            'tool': 'run_script',
            'path': str(prep.path),
            'args': prep.argv[1:],
            'duration_ms': result.get('duration_ms'),
            'exitCode': result.get('exitCode'),
            'truncated': result.get('truncated', False),
            'result': {'ok': result.get('exitCode', 1) == 0},
        }
        with open(fp, 'a', encoding='utf-8') as f:
            f.write(json.dumps(line, ensure_ascii=False) + '\n')
    except Exception as e:
        logging.getLogger('test-start-mcp').debug('audit log failed: %s', e)


def run_sync(prep: Prepared) -> Dict[str, Any]:
    start = time.time()
    try:
        proc = subprocess.Popen(
            prep.argv,
            cwd=str(prep.cwd),
            env=prep.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            out, err = proc.communicate(timeout=prep.timeout_ms / 1000.0)
            exit_code = proc.returncode
            duration_ms = int((time.time() - start) * 1000)
            truncated = False
            out, t1 = _truncate_text(out or '', prep.max_output_bytes)
            err, t2 = _truncate_text(err or '', prep.max_output_bytes)
            truncated = t1 or t2
            res = {
                'exitCode': int(exit_code),
                'duration_ms': duration_ms,
                'stdout': out,
                'stderr': err,
                'truncated': truncated,
            }
            _audit_log(prep, res)
            return res
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            duration_ms = int((time.time() - start) * 1000)
            res = {
                'exitCode': -1,
                'duration_ms': duration_ms,
                'stderr': 'timeout',
                'truncated': True,
            }
            _audit_log(prep, res)
            return res
    except FileNotFoundError:
        return {'exitCode': 127, 'duration_ms': 0, 'stderr': 'not found', 'truncated': False}
    except Exception as e:
        return {'exitCode': 1, 'duration_ms': 0, 'stderr': str(e), 'truncated': False}


def stream_process(prep: Prepared) -> Iterable[Dict[str, Any]]:
    start = time.time()
    try:
        proc = subprocess.Popen(
            prep.argv,
            cwd=str(prep.cwd),
            env=prep.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        last_ping = 0.0
        # Non-blocking, iterate line-by-line
        while True:
            now = time.time()
            if now - last_ping > 5.0:
                yield {'event': 'ping', 'data': {'t': int(now)}}
                last_ping = now
            if proc.poll() is not None:
                break
            # Drain available lines (best-effort)
            if proc.stdout is not None:
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    s, _ = _truncate_text(line.rstrip('\n'), prep.max_line_bytes)
                    yield {'event': 'stdout', 'data': {'line': s}}
            if proc.stderr is not None:
                while True:
                    line = proc.stderr.readline()
                    if not line:
                        break
                    s, _ = _truncate_text(line.rstrip('\n'), prep.max_line_bytes)
                    yield {'event': 'stderr', 'data': {'line': s}}
            if (now - start) * 1000.0 > prep.timeout_ms:
                try:
                    proc.kill()
                except Exception:
                    pass
                dur = int((time.time() - start) * 1000)
                yield {'event': 'end', 'data': {'exitCode': -1, 'duration_ms': dur, 'truncated': True}}
                return
            time.sleep(0.05)

        exit_code = proc.returncode or 0
        dur = int((time.time() - start) * 1000)
        yield {'event': 'end', 'data': {'exitCode': int(exit_code), 'duration_ms': dur}}
    except Exception as e:
        yield {'event': 'error', 'data': {'code': 'E_EXEC', 'message': str(e)}}


def tool_schemas() -> List[Dict[str, Any]]:
    return [
        {
            'name': 'run_script',
            'title': 'Run Allowed Script',
            'description': 'Run an allowlisted script with validated args; returns stdout/stderr and status.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string'},
                    'args': {'type': 'array', 'items': {'type': 'string'}},
                    'env': {'type': 'object'},
                    'timeout_ms': {'type': 'integer', 'default': _env_int('TSM_TIMEOUT_MS_DEFAULT', 90_000)},
                },
                'required': ['path']
            },
            'outputSchema': {
                'type': 'object',
                'properties': {
                    'exitCode': {'type': 'integer'},
                    'duration_ms': {'type': 'integer'},
                    'stdout': {'type': 'string'},
                    'stderr': {'type': 'string'},
                    'truncated': {'type': 'boolean'},
                    'logPath': {'type': ['string','null']},
                },
                'required': ['exitCode','duration_ms']
            }
        },
        {
            'name': 'list_allowed',
            'title': 'List Allowed Scripts',
            'description': 'Return allowlisted scripts and allowed argument flags.',
            'inputSchema': {'type': 'object', 'properties': {}},
            'outputSchema': {'type': 'object', 'properties': {'scripts': {'type': 'array', 'items': {'type': 'object'}}}, 'required': ['scripts']}
        }
    ]

