#!/usr/bin/env python3
import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, Request, Query
    from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import uvicorn
except Exception:
    print("Missing dependencies: fastapi, uvicorn")
    print("Create a venv and: pip install fastapi uvicorn")
    raise SystemExit(1)

try:
    # module import
    from .policy import (
        PROTOCOL_VERSION,
        list_allowed_scripts,
        validate_and_prepare,
        run_sync,
        stream_process,
        auth_ok,
        tool_schemas,
    )
    from .policy_store import load_state, save_state, evaluate_preflight, PolicyState, Rule, Overlay, Caps, Profile, effective_caps_for
except Exception:
    # script import
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from policy import (
        PROTOCOL_VERSION,
        list_allowed_scripts,
        validate_and_prepare,
        run_sync,
        stream_process,
        auth_ok,
        tool_schemas,
    )
    from policy_store import load_state, save_state, evaluate_preflight, PolicyState, Rule, Overlay, Caps, Profile, effective_caps_for


def create_app() -> FastAPI:
    app = FastAPI()

    # Basic logging; TSM_LOG_LEVEL=DEBUG|INFO|WARNING
    lvl = os.environ.get('TSM_LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(level=getattr(logging, lvl, logging.INFO), format='[%(levelname)s] %(message)s')
    LOG = logging.getLogger('test-start-mcp')

    # Static files and templates (for UI pages)
    try:
        static_dir = Path(__file__).parent / 'static'
        templates_dir = Path(__file__).parent / 'templates'
        app.mount('/static', StaticFiles(directory=str(static_dir)), name='static')
        templates = Jinja2Templates(directory=str(templates_dir))
    except Exception as e:
        LOG.error(f"Templates initialization failed: {e}")
        templates = None  # In case of missing fastapi optional deps; UI routes will fallback

    # In-memory preflight cache: (sessionId,path,args) -> timestamp ms
    _pref_cache: Dict[str, int] = {}

    def _pref_key(sess: Optional[str], path: str, args: List[str]) -> Optional[str]:
        if not sess:
            return None
        try:
            rp = str(Path(path).resolve())
        except Exception:
            rp = str(path)
        return f"{sess}:::{rp}:::{'\u0001'.join(args or [])}"

    def _pref_ttl_sec() -> int:
        try:
            return int(os.environ.get('TSM_PREFLIGHT_TTL_SEC', '600').strip())
        except Exception:
            return 600

    def _require_pref_ok(session_id: Optional[str], path: str, args: List[str]) -> Optional[Dict[str, Any]]:
        enforce = os.environ.get('TSM_REQUIRE_PREFLIGHT', '0')
        if str(enforce).lower() not in ('1', 'true', 'yes'):
            return None
        k = _pref_key(session_id, path, list(args))
        if not k:
            return {'error': 'E_POLICY', 'message': 'preflight_required: missing sessionId (X-TSM-Session)'}
        import time
        now = int(time.time() * 1000)
        t = _pref_cache.get(k)
        if t is None:
            return {'error': 'E_POLICY', 'message': 'preflight_required'}
        if now - t > _pref_ttl_sec() * 1000:
            return {'error': 'E_POLICY', 'message': 'preflight_expired'}
        return None

    def _record_pref(session_id: Optional[str], path: str, args: List[str]) -> None:
        k = _pref_key(session_id, path, list(args))
        if not k:
            return
        import time
        _pref_cache[k] = int(time.time() * 1000)

    @app.get('/healthz')
    def healthz():
        """Enhanced health check with script validation"""
        health = {
            'ok': True,
            'name': 'Test-Start-MCP',
            'version': PROTOCOL_VERSION,
            'checks': {}
        }

        # Check environment configuration
        try:
            allowed_root = os.environ.get('TSM_ALLOWED_ROOT')
            if allowed_root and Path(allowed_root).exists():
                health['checks']['allowed_root'] = {'status': 'ok', 'path': allowed_root}
            else:
                health['checks']['allowed_root'] = {'status': 'warning', 'message': 'TSM_ALLOWED_ROOT not set or path does not exist'}

            # Check allowed scripts
            scripts = list_allowed_scripts()
            valid_scripts = 0
            invalid_scripts = []

            for script_info in scripts:
                script_path = Path(script_info['path'])
                if script_path.exists() and script_path.is_file():
                    # Check if executable
                    if os.access(script_path, os.X_OK):
                        valid_scripts += 1
                    else:
                        invalid_scripts.append({'path': str(script_path), 'issue': 'not_executable'})
                else:
                    invalid_scripts.append({'path': str(script_path), 'issue': 'not_found'})

            health['checks']['scripts'] = {
                'status': 'ok' if not invalid_scripts else 'warning',
                'valid_count': valid_scripts,
                'invalid_count': len(invalid_scripts),
                'invalid_scripts': invalid_scripts[:5]  # Limit to 5 for brevity
            }

            # Check log directory
            log_dir = Path(os.environ.get('TSM_LOG_DIR', 'Test-Start-MCP/logs'))
            if log_dir.exists() and log_dir.is_dir():
                health['checks']['logging'] = {'status': 'ok', 'log_dir': str(log_dir)}
            else:
                health['checks']['logging'] = {'status': 'info', 'message': 'Log directory will be created on first execution'}

            # Overall health
            if invalid_scripts or not allowed_root:
                health['ok'] = False

        except Exception as e:
            health['ok'] = False
            health['checks']['validation_error'] = {'status': 'error', 'message': str(e)}

        return health

    # ---- REST endpoints ----
    @app.post('/actions/list_allowed')
    async def http_list_allowed(request: Request):
        if not auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        scripts = list_allowed_scripts()
        return JSONResponse({'scripts': scripts})

    @app.post('/actions/search_logs')
    async def http_search_logs(request: Request):
        """Search through execution logs"""
        if not auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)

        body = await request.json()
        query = body.get('query', '')
        limit = min(body.get('limit', 50), 500)  # Max 500 results

        import json
        import time
        from pathlib import Path

        log_dir = Path(os.environ.get('TSM_LOG_DIR', 'Test-Start-MCP/logs'))
        results = []

        if not log_dir.exists():
            return JSONResponse({'results': [], 'message': 'No logs directory'})

        # Search last 7 days of logs
        for i in range(7):
            date = time.strftime('%Y%m%d', time.gmtime(time.time() - i * 86400))
            log_file = log_dir / f'exec-{date}.jsonl'

            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        for line in f:
                            if line.strip():
                                try:
                                    log_data = json.loads(line.strip())
                                    # Simple text search in path, args, and result
                                    text_to_search = f"{log_data.get('path', '')} {' '.join(log_data.get('args', []))} {log_data.get('tool', '')}"
                                    if query.lower() in text_to_search.lower():
                                        results.append(log_data)
                                        if len(results) >= limit:
                                            break
                                except json.JSONDecodeError:
                                    continue
                except Exception:
                    continue

                if len(results) >= limit:
                    break

        return JSONResponse({'results': results[:limit], 'total_found': len(results)})

    @app.post('/actions/get_stats')
    async def http_get_stats(request: Request):
        """Get execution statistics"""
        if not auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)

        import json
        import time
        from pathlib import Path
        from collections import defaultdict

        log_dir = Path(os.environ.get('TSM_LOG_DIR', 'Test-Start-MCP/logs'))
        stats = {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'avg_duration_ms': 0,
            'most_used_scripts': defaultdict(int),
            'recent_errors': []
        }

        if not log_dir.exists():
            return JSONResponse(dict(stats))

        total_duration = 0

        # Analyze last 7 days
        for i in range(7):
            date = time.strftime('%Y%m%d', time.gmtime(time.time() - i * 86400))
            log_file = log_dir / f'exec-{date}.jsonl'

            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        for line in f:
                            if line.strip():
                                try:
                                    log_data = json.loads(line.strip())
                                    stats['total_executions'] += 1

                                    if log_data.get('exitCode') == 0:
                                        stats['successful_executions'] += 1
                                    else:
                                        stats['failed_executions'] += 1
                                        if len(stats['recent_errors']) < 5:
                                            stats['recent_errors'].append({
                                                'path': log_data.get('path'),
                                                'exitCode': log_data.get('exitCode'),
                                                'ts': log_data.get('ts')
                                            })

                                    duration = log_data.get('duration_ms', 0)
                                    total_duration += duration

                                    script_path = log_data.get('path', 'unknown')
                                    stats['most_used_scripts'][script_path] += 1

                                except json.JSONDecodeError:
                                    continue
                except Exception:
                    continue

        if stats['total_executions'] > 0:
            stats['avg_duration_ms'] = total_duration // stats['total_executions']

        # Convert defaultdict to regular dict and get top 5
        stats['most_used_scripts'] = dict(list(stats['most_used_scripts'].items())[:5])

        return JSONResponse(dict(stats))

    @app.post('/actions/run_script')
    async def http_run_script(request: Request):
        if not auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        body = await request.json()
        path = body.get('path') or ''
        args = body.get('args') or []
        env = body.get('env') or {}
        timeout_ms = body.get('timeout_ms')
        # Enforce preflight if enabled
        err_pref = _require_pref_ok(request.headers.get('X-TSM-Session'), path, list(args))
        if err_pref is not None:
            return JSONResponse(err_pref, status_code=428)
        ok, err, prep = validate_and_prepare(path, args, env, timeout_ms)
        if not ok:
            return JSONResponse({'error': err.get('code', 'error'), 'message': err.get('message')}, status_code=400 if err.get('code') != 'E_FORBIDDEN' else 403)
        # Enforce caps from policy (overlay/rule) by clamping timeout and output bytes
        try:
            state_fp = Path(os.environ.get('TSM_ALLOWED_FILE', str(Path(__file__).resolve().parents[1] / 'allowlist.json')))
            state = load_state(state_fp)
            allowed_root = Path(os.environ.get('TSM_ALLOWED_ROOT', str(Path(__file__).resolve().parents[1])))
            caps_eff = effective_caps_for(path, request.headers.get('X-TSM-Session'), allowed_root, state)
            if caps_eff:
                if isinstance(prep.timeout_ms, int):
                    prep.timeout_ms = min(prep.timeout_ms, int(caps_eff.maxTimeoutMs))
                if isinstance(prep.max_output_bytes, int):
                    prep.max_output_bytes = min(prep.max_output_bytes, int(caps_eff.maxBytes))
        except Exception:
            pass
        result = run_sync(prep)
        return JSONResponse(result)

    @app.get('/sse/logs_stream')
    async def http_logs_stream(request: Request):
        """Stream audit logs in real-time"""
        if not auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)

        import time
        import json
        from pathlib import Path

        def gen():
            log_dir = Path(os.environ.get('TSM_LOG_DIR', 'Test-Start-MCP/logs'))
            if not log_dir.exists():
                yield f"event: info\ndata: {json.dumps({'message': 'No logs directory found'})}\n\n"
                return

            # Get today's log file
            today = time.strftime('%Y%m%d')
            log_file = log_dir / f'exec-{today}.jsonl'

            if not log_file.exists():
                yield f"event: info\ndata: {json.dumps({'message': 'No logs for today'})}\n\n"
                return

            try:
                # Read existing logs
                with open(log_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            try:
                                log_data = json.loads(line.strip())
                                yield f"event: log\ndata: {json.dumps(log_data)}\n\n"
                            except json.JSONDecodeError:
                                continue

                yield f"event: info\ndata: {json.dumps({'message': 'End of existing logs'})}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(gen(), media_type='text/event-stream')

    @app.get('/sse/run_script_stream')
    async def http_run_script_stream(
        request: Request,
        path: str = Query(...),
        args: Optional[str] = Query(None, description='JSON array of args or comma-separated'),
        timeout_ms: Optional[int] = Query(None),
    ):
        if not auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        # Parse args from query
        parsed_args: List[str]
        if args is None or args == '':
            parsed_args = []
        else:
            try:
                a = args.strip()
                if a.startswith('['):
                    parsed_args = list(json.loads(a))
                elif ',' in a:
                    parsed_args = [s.strip() for s in a.split(',') if s.strip()]
                else:
                    parsed_args = [tok for tok in a.split() if tok]
            except Exception:
                return JSONResponse({'error': 'E_BAD_ARG', 'message': 'args must be JSON array, comma-separated, or space-separated string'}, status_code=400)
        # Enforce preflight if enabled
        err_pref = _require_pref_ok(request.headers.get('X-TSM-Session'), path, list(parsed_args))
        if err_pref is not None:
            return JSONResponse(err_pref, status_code=428)
        ok, err, prep = validate_and_prepare(path, parsed_args, {}, timeout_ms)
        if not ok:
            return JSONResponse({'error': err.get('code', 'error'), 'message': err.get('message')}, status_code=400 if err.get('code') != 'E_FORBIDDEN' else 403)
        # Clamp runtime caps
        try:
            state_fp = Path(os.environ.get('TSM_ALLOWED_FILE', str(Path(__file__).resolve().parents[1] / 'allowlist.json')))
            state = load_state(state_fp)
            allowed_root = Path(os.environ.get('TSM_ALLOWED_ROOT', str(Path(__file__).resolve().parents[1])))
            caps_eff = effective_caps_for(path, request.headers.get('X-TSM-Session'), allowed_root, state)
            if caps_eff:
                if isinstance(prep.timeout_ms, int):
                    prep.timeout_ms = min(prep.timeout_ms, int(caps_eff.maxTimeoutMs))
                if isinstance(prep.max_output_bytes, int):
                    prep.max_output_bytes = min(prep.max_output_bytes, int(caps_eff.maxBytes))
        except Exception:
            pass

        def gen():
            try:
                for ev in stream_process(prep):
                    yield f"event: {ev['event']}\n" + f"data: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"event: error\n" + f"data: {json.dumps({'code': 'E_EXEC', 'message': str(e)})}\n\n"

        return StreamingResponse(gen(), media_type='text/event-stream')

    # ---- MCP JSON-RPC endpoint ----
    def mcp_tools() -> List[Dict[str, Any]]:
        tools = tool_schemas()
        for t in tools:
            if t.get('name') == 'run_script':
                t['description'] = (
                    'Execute a pre‑approved script with validated flags (no shell). '
                    'Built for safe local starts and smoke tests: allowlists, timeouts, output truncation, and JSONL audit logs. '
                    'Returns stdout/stderr and status; includes logPath to the audit file.'
                )
                # Non-standard guidance hint to agents
                t['x-guidance'] = {
                    'useAfter': 'check_script',
                    'requiresPreflight': os.environ.get('TSM_REQUIRE_PREFLIGHT', '0').lower() in ('1','true','yes')
                }
            elif t.get('name') == 'list_allowed':
                t['description'] = (
                    'List the scripts and flags explicitly allowed on this host so you can choose safe entry points before run_script.'
                )
        # Append check_script tool stub
        tools.append({
            'name': 'check_script',
            'title': 'Pre‑flight Script',
            'description': 'Pre‑flight a path+args against policy; returns allowed, reasons, suggestions, and adminLink to configure policy.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string'},
                    'args': {'type': 'array', 'items': {'type': 'string'}},
                },
                'required': ['path']
            },
            'outputSchema': {
                'type': 'object',
                'properties': {
                    'allowed': {'type': 'boolean'},
                    'reasons': {'type': 'array', 'items': {'type': 'string'}},
                    'matchedRule': {'type': ['object','null']},
                    'suggestions': {'type': 'array', 'items': {'type': 'object'}},
                    'adminLink': {'type': 'string'}
                },
                'required': ['allowed','reasons','adminLink']
            },
            'x-guidance': { 'useBefore': 'run_script' }
        })
        return tools

    def _mcp_response(id_value, result=None, error=None):
        if error is not None:
            return {'jsonrpc': '2.0', 'id': id_value, 'error': error}
        return {'jsonrpc': '2.0', 'id': id_value, 'result': result}

    # Stable session id for MCP guidance (not required for auth)
    import uuid as _uuid
    _MCP_SESSION_ID = os.environ.get('TSM_MCP_SESSION_ID') or f"sess-{_uuid.uuid4().hex[:8]}"

    @app.post('/mcp')
    async def mcp_endpoint(request: Request):
        if not auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({'error': 'invalid json'}, status_code=400)

        async def handle_one(msg: Dict[str, Any]):
            msg_id = msg.get('id')
            method = msg.get('method') or ''

            if method == 'initialize':
                # Embed guidance for agents: preflight policy and admin link
                enforced = os.environ.get('TSM_REQUIRE_PREFLIGHT', '0').lower() in ('1','true','yes')
                ttl_sec = 0
                try:
                    ttl_sec = int(os.environ.get('TSM_PREFLIGHT_TTL_SEC', '600'))
                except Exception:
                    ttl_sec = 600
                allowed_root = os.environ.get('TSM_ALLOWED_ROOT', str(Path(__file__).resolve().parents[1]))
                instructions = (
                    'Pre‑flight before run: call check_script; if not allowed, open the admin link and add a TTL‑bound rule; '
                    'then re‑check and run. Use the X-TSM-Session header if preflight is enforced.'
                )
                return _mcp_response(msg_id, result={
                    'protocolVersion': PROTOCOL_VERSION,
                    'capabilities': {'tools': {}},
                    'serverInfo': {'name': 'Test-Start-MCP', 'version': PROTOCOL_VERSION},
                    'policy': {
                        'preflight': {
                            'recommended': True,
                            'enforced': enforced,
                            'checkTool': 'check_script',
                            'sessionHeader': 'X-TSM-Session',
                            'ttlSec': ttl_sec,
                            'adminLink': '/admin'
                        },
                        'allowedRoot': allowed_root
                    },
                    'session': {
                        'id': _MCP_SESSION_ID,
                        'header': 'X-TSM-Session'
                    },
                    'instructions': instructions,
                })

            if method == 'notifications/initialized':
                return None  # notification

            if method == 'tools/list':
                return _mcp_response(msg_id, result={'tools': mcp_tools()})

            if method == 'tools/call':
                params = msg.get('params') or {}
                name = params.get('name') or ''
                arguments = params.get('arguments') or {}
                try:
                    if name == 'run_script':
                        path = arguments.get('path') or ''
                        args = arguments.get('args') or []
                        env = arguments.get('env') or {}
                        timeout_ms = arguments.get('timeout_ms')
                        # Enforce preflight if enabled (session via header)
                        session_id = request.headers.get('X-TSM-Session')
                        err_pref = _require_pref_ok(session_id, path, list(args))
                        if err_pref is not None:
                            return _mcp_response(msg_id, result={'content': [{'type': 'text', 'text': err_pref.get('message', 'preflight required')}], 'structuredContent': {'error': {'code': 'E_POLICY', 'message': err_pref.get('message')}}, 'isError': True})
                        ok, err, prep = validate_and_prepare(path, args, env, timeout_ms)
                        if not ok:
                            return _mcp_response(msg_id, result={'content': [{'type': 'text', 'text': err.get('message', 'error')}], 'structuredContent': {'error': err}, 'isError': True})
                        # Clamp runtime caps
                        try:
                            state_fp = Path(os.environ.get('TSM_ALLOWED_FILE', str(Path(__file__).resolve().parents[1] / 'allowlist.json')))
                            state = load_state(state_fp)
                            allowed_root = Path(os.environ.get('TSM_ALLOWED_ROOT', str(Path(__file__).resolve().parents[1])))
                            caps_eff = effective_caps_for(path, request.headers.get('X-TSM-Session'), allowed_root, state)
                            if caps_eff:
                                if isinstance(prep.timeout_ms, int):
                                    prep.timeout_ms = min(prep.timeout_ms, int(caps_eff.maxTimeoutMs))
                                if isinstance(prep.max_output_bytes, int):
                                    prep.max_output_bytes = min(prep.max_output_bytes, int(caps_eff.maxBytes))
                        except Exception:
                            pass
                        res = run_sync(prep)
                        return _mcp_response(msg_id, result={'content': [{'type': 'text', 'text': f"exit {res['exitCode']} ({res['duration_ms']}ms)"}], 'structuredContent': res, 'isError': False})
                    if name == 'list_allowed':
                        scripts = list_allowed_scripts()
                        return _mcp_response(msg_id, result={'content': [{'type': 'text', 'text': f"{len(scripts)} scripts"}], 'structuredContent': {'scripts': scripts}})
                    if name == 'check_script':
                        pth = arguments.get('path') or ''
                        arg_list = arguments.get('args') or []
                        state_fp = Path(os.environ.get('TSM_ALLOWED_FILE', str(Path(__file__).resolve().parents[1] / 'allowlist.json')))
                        state = load_state(state_fp)
                        allowed_root = Path(os.environ.get('TSM_ALLOWED_ROOT', str(Path(__file__).resolve().parents[1])))
                        flags_global: List[str] = []
                        raw = os.environ.get('TSM_ALLOWED_ARGS', '')
                        for part in raw.replace(';', ':').split(':'):
                            for a in part.split(','):
                                a = a.strip()
                                if a:
                                    flags_global.append(a)
                        session_id = request.headers.get('X-TSM-Session')
                        allowed, matched, reasons, suggestions = evaluate_preflight(pth, arg_list, session_id, None, None, allowed_root, flags_global, state)
                        admin_link = '/admin/new?path=' + str(pth)
                        if allowed:
                            _record_pref(session_id, str(pth), list(arg_list))
                        return _mcp_response(msg_id, result={
                            'content': [{'type': 'text', 'text': ('Allowed' if allowed else 'Not allowed') }],
                            'structuredContent': {
                                'allowed': allowed,
                                'reasons': reasons,
                                'matchedRule': matched,
                                'suggestions': suggestions,
                                'adminLink': admin_link,
                            },
                            'isError': False,
                        })
                except Exception as e:
                    logging.getLogger('test-start-mcp').exception('tools/call failed: %s', e)
                    return _mcp_response(msg_id, result={'content': [{'type': 'text', 'text': f'Error: {e}'}], 'structuredContent': {'error': {'code': 'E_EXEC', 'message': str(e)}}, 'isError': True})

            # Unknown method
            return _mcp_response(msg_id, error={'code': -32601, 'message': f'Unknown method: {method}'})

        if isinstance(body, list):
            out = []
            for m in body:
                resp = await handle_one(m)
                if resp is not None:
                    out.append(resp)
            if not out:
                return JSONResponse(status_code=202, content=None)
            # If batch includes initialize, include guidance headers
            try:
                has_init = any(isinstance(m, dict) and (m.get('method') or '') == 'initialize' for m in body)
            except Exception:
                has_init = False
            headers = None
            if has_init:
                enforced = os.environ.get('TSM_REQUIRE_PREFLIGHT', '0').lower() in ('1','true','yes')
                headers = {
                    'X-TSM-Preflight': ('required' if enforced else 'recommended'),
                    'Mcp-Session-Id': _MCP_SESSION_ID,
                }
            return JSONResponse(out, headers=headers or None)
        elif isinstance(body, dict):
            resp = await handle_one(body)
            if resp is None:
                return JSONResponse(status_code=202, content=None)
            # If this is initialize, include guidance headers
            is_init = (body.get('method') or '') == 'initialize'
            headers = None
            if is_init:
                enforced = os.environ.get('TSM_REQUIRE_PREFLIGHT', '0').lower() in ('1','true','yes')
                headers = {
                    'X-TSM-Preflight': ('required' if enforced else 'recommended'),
                    'Mcp-Session-Id': _MCP_SESSION_ID,
                }
            return JSONResponse(resp, headers=headers or None)
        else:
            return JSONResponse({'error': 'invalid payload'}, status_code=400)

    @app.get('/mcp_ui')
    async def mcp_ui(request: Request):
        if templates is not None:
            return templates.TemplateResponse('mcp-ui.html', {'request': request})
        from pathlib import Path as _P
        _default_script = str(_P(__file__).resolve().parents[1] / 'run-tests-and-server.sh')
        html = """
        <!DOCTYPE html>
        <html>
        <head>
          <title>Test-Start-MCP (MCP UI)</title>
          <style>
            body { font-family: system-ui, sans-serif; background: #0b1220; color: #e0e6f0; padding: 20px; }
            section { background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
            label { display: block; margin: 6px 0; }
            input, textarea { width: 100%; background: #0b1220; color: #e0e6f0; border: 1px solid #374151; border-radius: 6px; padding: 8px; }
            button { background: #2563eb; color: white; border: 0; border-radius: 6px; padding: 8px 12px; cursor: pointer; margin-right: 6px; }
            pre { background: #0b1220; border: 1px solid #1f2937; border-radius: 8px; padding: 10px; max-height: 50vh; overflow: auto; }
            small { color: #94a3b8; }
          </style>
        </head>
        <body>
          <h1>Test‑Start‑MCP — MCP UI</h1>
          <small>Authorization uses TSM_TOKEN from localStorage if set.</small>
          <section>
            <h2>Initialize</h2>
            <label>Protocol <input id="proto" value="2025-06-18"/></label>
            <button onclick="initMcp()">initialize</button>
            <pre id="initOut">(not initialized)</pre>
          </section>
          <section>
            <h2>Tools</h2>
            <button onclick="listTools()">tools/list</button>
            <pre id="toolsOut">(no tools)</pre>
          </section>
          <section>
            <h2>Call Tool</h2>
            <label>Tool name <input id="tname" value="run_script"/></label>
            <label>Arguments (JSON)
              <textarea id="targs" rows="6">{}</textarea></label>
            <button onclick="callTool()">tools/call</button>
            <pre id="callOut">(no call)</pre>
          </section>
          <script>
            function headers(){
              const t = localStorage.getItem('TSM_TOKEN') || '';
              const h = {'Content-Type':'application/json','Accept':'application/json'};
              if (t) h['Authorization'] = 'Bearer '+t;
              return h;
            }
            function j(o){try{return JSON.stringify(o,null,2);}catch(e){return String(o);} }
            async function initMcp(){
              const p = document.getElementById('proto').value || '2025-06-18';
              const body = { jsonrpc:'2.0', id:1, method:'initialize', params:{ protocolVersion:p, capabilities:{}, clientInfo:{ name:'mcp-ui', version:'1' } } };
              const r = await fetch('/mcp', { method:'POST', headers: headers(), body: JSON.stringify(body) });
              document.getElementById('initOut').textContent = j(await r.json());
            }
            async function listTools(){
              const body = [{ jsonrpc:'2.0', id:1, method:'initialize', params:{ protocolVersion:'2025-06-18', capabilities:{}, clientInfo:{ name:'mcp-ui', version:'1' } } },
                            { jsonrpc:'2.0', id:2, method:'tools/list' }];
              const r = await fetch('/mcp', { method:'POST', headers: headers(), body: JSON.stringify(body) });
              document.getElementById('toolsOut').textContent = j(await r.json());
            }
            async function callTool(){
              let args = {};
              try { args = JSON.parse(document.getElementById('targs').value || '{}'); } catch(e){ alert('Invalid JSON for arguments'); return; }
              const name = document.getElementById('tname').value || '';
              const body = { jsonrpc:'2.0', id:3, method:'tools/call', params:{ name, arguments: args } };
              const r = await fetch('/mcp', { method:'POST', headers: headers(), body: JSON.stringify(body) });
              document.getElementById('callOut').textContent = j(await r.json());
            }
          </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html)

    @app.get('/start')
    async def start_ui(request: Request):
        if templates is not None:
            _default_script = str(Path(__file__).resolve().parents[1] / 'run-tests-and-server.sh')
            return templates.TemplateResponse('start.html', {'request': request, 'default_script': _default_script})
        from pathlib import Path as _P
        _default_script = str(_P(__file__).resolve().parents[1] / 'run-tests-and-server.sh')
        html = """
        <!DOCTYPE html>
        <html>
        <head>
          <title>Test-Start-MCP UI</title>
          <style>
            body { font-family: system-ui, sans-serif; background: #0b1220; color: #e0e6f0; padding: 20px; }
            section { background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
            label { display: block; margin: 6px 0; }
            input, textarea { width: 100%; background: #0b1220; color: #e0e6f0; border: 1px solid #374151; border-radius: 6px; padding: 8px; }
            button { background: #2563eb; color: white; border: 0; border-radius: 6px; padding: 8px 12px; cursor: pointer; margin-right: 6px; }
            pre { background: #0b1220; border: 1px solid #1f2937; border-radius: 8px; padding: 10px; max-height: 50vh; overflow: auto; }
            small { color: #94a3b8; }
            .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
          </style>
        </head>
        <body>
          <h1>Test‑Start‑MCP — UI</h1>
          <small>Authorization uses TSM_TOKEN from localStorage if set.</small>

          <section>
            <h2>Allowed Scripts</h2>
            <button onclick="loadAllowed()">List Allowed</button>
            <pre id="allowedOut">(none)</pre>
          </section>

          <section>
            <h2>Run Script (REST)</h2>
            <label>Path <input id="sp"/></label>
            <label>Args (comma or JSON array) <input id="sa" value="--no-tests,--smoke"/></label>
            <label>Timeout (ms) <input id="st" value="30000"/></label>
            <button onclick="runScript()">POST /actions/run_script</button>
            <pre id="runOut">(no result)</pre>
          </section>

          <section>
            <h2>Run Script (SSE)</h2>
            <label>Path <input id="ssp"/></label>
            <label>Args (comma or JSON array) <input id="ssa" value="--no-tests,--smoke"/></label>
            <label>Timeout (ms) <input id="sst" value="30000"/></label>
            <button onclick="startStream()">Open SSE</button>
            <button onclick="stopStream()">Close SSE</button>
            <pre id="streamOut">(no stream)</pre>
          </section>

          <div class="row">
            <section>
              <h2>Logs Stream</h2>
              <button onclick="openLogs()">Open Logs SSE</button>
              <button onclick="closeLogs()">Close</button>
              <pre id="logsOut">(no logs)</pre>
            </section>
            <section>
              <h2>Stats & Health</h2>
              <button onclick="getStats()">POST /actions/get_stats</button>
              <button onclick="health()">GET /healthz</button>
              <pre id="statsOut">(no stats)</pre>
              <pre id="healthOut">(no health)</pre>
            </section>
          </div>

          <script>
            const DEFAULT_SCRIPT = 
          </script>
        </body>
        </html>
        """
        html = html.replace('const DEFAULT_SCRIPT = ', 'const DEFAULT_SCRIPT = ' + json.dumps(_default_script) + ';\n')
        js = """
            let es=null; let esLogs=null;
            function headers(){
              const t = localStorage.getItem('TSM_TOKEN') || '';
              const h = {'Content-Type':'application/json','Accept':'application/json'};
              if (t) h['Authorization'] = 'Bearer '+t; return h;
            }
            function j(o){ try { return JSON.stringify(o, null, 2) } catch(e){ return String(o) } }
            function parseArgs(s){
              if (!s) return [];
              const t = s.trim();
              if (t.startsWith('[')) { try { return JSON.parse(t) } catch(e){ return [] } }
              return t.split(',').map(x=>x.trim()).filter(Boolean);
            }
            (function(){
              const a = document.getElementById('sp'); if (a) a.value = DEFAULT_SCRIPT;
              const b = document.getElementById('ssp'); if (b) b.value = DEFAULT_SCRIPT;
            })();
            async function loadAllowed(){
              const r = await fetch('/actions/list_allowed', {method:'POST', headers: headers(), body: '{}'});
              document.getElementById('allowedOut').textContent = j(await r.json());
            }
            async function runScript(){
              const path = document.getElementById('sp').value;
              const args = parseArgs(document.getElementById('sa').value);
              const timeout_ms = parseInt(document.getElementById('st').value||'0')||null;
              const body = { path, args, timeout_ms };
              const r = await fetch('/actions/run_script', {method:'POST', headers: headers(), body: JSON.stringify(body)});
              document.getElementById('runOut').textContent = j(await r.json());
            }
            function startStream(){
              stopStream();
              const path = document.getElementById('ssp').value;
              const args = document.getElementById('ssa').value;
              const timeout_ms = parseInt(document.getElementById('sst').value||'0')||null;
              const q = new URLSearchParams();
              q.set('path', path);
              if (args) q.set('args', args);
              if (timeout_ms) q.set('timeout_ms', String(timeout_ms));
              const url = '/sse/run_script_stream?' + q.toString();
              const out = document.getElementById('streamOut');
              out.textContent = '';
              es = new EventSource(url);
              es.onmessage = (ev)=>{ out.textContent += ev.data + "\n" };
              es.addEventListener('stdout', ev=>{ out.textContent += '[stdout] '+ev.data+"\n" });
              es.addEventListener('stderr', ev=>{ out.textContent += '[stderr] '+ev.data+"\n" });
              es.addEventListener('end', ev=>{ out.textContent += '[end] '+ev.data+"\n" });
              es.addEventListener('error', ev=>{ out.textContent += '[error] '+ev.data+"\n" });
            }
            function stopStream(){ if (es){ es.close(); es=null; } }
            function openLogs(){
              closeLogs();
              const out = document.getElementById('logsOut'); out.textContent='';
              esLogs = new EventSource('/sse/logs_stream');
              esLogs.addEventListener('log', ev=>{ out.textContent += ev.data+"\n" });
              esLogs.onmessage = (ev)=>{ out.textContent += ev.data+"\n" };
              esLogs.addEventListener('info', ev=>{ out.textContent += '[info] '+ev.data+"\n" });
              esLogs.addEventListener('error', ev=>{ out.textContent += '[error] '+ev.data+"\n" });
            }
            function closeLogs(){ if (esLogs){ esLogs.close(); esLogs=null; } }
            async function getStats(){
              const r = await fetch('/actions/get_stats', {method:'POST', headers: headers(), body: '{}'});
              document.getElementById('statsOut').textContent = j(await r.json());
            }
            async function health(){
              const r = await fetch('/healthz');
              document.getElementById('healthOut').textContent = j(await r.json());
            }
            window.loadAllowed = loadAllowed;
            window.runScript = runScript;
            window.startStream = startStream;
            window.stopStream = stopStream;
            window.openLogs = openLogs;
            window.closeLogs = closeLogs;
            window.getStats = getStats;
            window.health = health;
        """
        html = html.replace('</script>', js + '\n</script>')
        return HTMLResponse(content=html)

    # ---- Preflight (read-only) ----
    @app.post('/actions/check_script')
    async def http_check_script(request: Request):
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({'error': 'invalid json'}, status_code=400)
        path = body.get('path') or ''
        args = body.get('args') or []
        session_id = body.get('sessionId') or request.headers.get('X-TSM-Session')
        # Load state file if configured
        state_fp = Path(os.environ.get('TSM_ALLOWED_FILE', str(Path(__file__).resolve().parents[1] / 'allowlist.json')))
        state: Optional[PolicyState] = load_state(state_fp)
        allowed_root = Path(os.environ.get('TSM_ALLOWED_ROOT', str(Path(__file__).resolve().parents[1])))
        flags_global = []
        allowed_args_raw = os.environ.get('TSM_ALLOWED_ARGS', '')
        for part in allowed_args_raw.replace(';', ':').split(':'):
            for a in part.split(','):
                a = a.strip()
                if a:
                    flags_global.append(a)
        allowed, matched, reasons, suggestions = evaluate_preflight(path, args, session_id, None, None, allowed_root, flags_global, state)
        admin_link = '/admin/new?path=' + str(path)
        if allowed:
            _record_pref(session_id, str(path), list(args))
        return JSONResponse({
            'allowed': allowed,
            'matchedRule': matched,
            'reasons': reasons,
            'suggestions': suggestions,
            'adminLink': admin_link,
        })

    # ---- Admin stubs (token required) ----
    def _admin_ok(req: Request) -> bool:
        token = os.environ.get('TSM_ADMIN_TOKEN')
        if not token:
            return False
        # Check Authorization header
        hdr = req.headers.get('Authorization','')
        if hdr.startswith('Bearer '):
            return hdr.split(' ',1)[1].strip() == token.strip()
        # Also check URL parameter for browser convenience
        if req.query_params.get('admin_token') == token.strip():
            return True
        return False

    @app.get('/admin')
    async def admin_ui(request: Request):
        if not _admin_ok(request):
            return HTMLResponse('<h1>Unauthorized</h1>', status_code=401)
        if templates is not None:
            return templates.TemplateResponse('admin.html', {'request': request})
        html = """
        <!DOCTYPE html>
        <html><head><title>Test-Start-MCP Admin</title>
        <style>
          body{font-family:system-ui,sans-serif;background:#0b1220;color:#e0e6f0;padding:20px}
          section{background:#111827;border:1px solid #1f2937;border-radius:8px;padding:12px;margin-bottom:12px}
          button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:6px 10px;margin-right:6px}
          input,select{background:#0b1220;color:#e0e6f0;border:1px solid #374151;border-radius:6px;padding:6px}
          table{width:100%;border-collapse:collapse}
          th,td{border-bottom:1px solid #1f2937;padding:6px;text-align:left}
          small{color:#94a3b8}
        </style>
        </head>
        <body>
          <h1>Admin — Test-Start-MCP</h1>
          <small>Token from localStorage TSM_ADMIN_TOKEN</small>
          <section>
            <button onclick="refresh()">Refresh State</button>
            <div id="state">(loading)</div>
          </section>
          <section>
            <h2>Rules</h2>
            <table id="rules"><thead><tr><th>ID</th><th>Type</th><th>Path/Scope</th><th>Patterns</th><th>Expires</th><th></th></tr></thead><tbody></tbody></table>
          </section>
          <section>
            <h2>Overlays</h2>
            <table id="overlays"><thead><tr><th>Session</th><th>Profile</th><th>Expires</th></tr></thead><tbody></tbody></table>
          </section>
          <section>
            <h2>Audit (policy)</h2>
            <button onclick="loadAudit()">Load Today's Audit</button>
            <pre id="audit">(none)</pre>
          </section>
          <script>
          function headers(){ const t = localStorage.getItem('TSM_ADMIN_TOKEN')||''; const h={'Content-Type':'application/json','Accept':'application/json'}; if(t) h['Authorization']='Bearer '+t; return h; }
          function j(o){try{return JSON.stringify(o,null,2)}catch(e){return String(o)}}
          async function refresh(){
            const r = await fetch('/admin/state', {headers: headers()});
            if(!r.ok){ document.getElementById('state').textContent='(unauthorized)'; return; }
            const st = await r.json();
            document.getElementById('state').textContent = j({version:st.version, profiles:Object.keys(st.profiles||{})});
            const tb = document.querySelector('#rules tbody'); tb.innerHTML='';
            (st.rules||[]).forEach(rule=>{
              const tr = document.createElement('tr');
              tr.innerHTML = `<td>${rule.id}</td><td>${rule.type}</td><td>${rule.path||rule.scopeRoot||''}</td><td>${(rule.patterns||[]).join(', ')}</td><td>${rule.expiresAt||''}</td><td><button data-id="${rule.id}">remove</button></td>`;
              tr.querySelector('button').onclick = async (ev)=>{
                const id = ev.target.getAttribute('data-id');
                const rr = await fetch('/admin/allowlist/remove', {method:'POST', headers: headers(), body: JSON.stringify({id})});
                await rr.json(); refresh();
              };
              tb.appendChild(tr);
            });
            const tob = document.querySelector('#overlays tbody'); tob.innerHTML='';
            (st.overlays||[]).forEach(o=>{
              const tr = document.createElement('tr');
              tr.innerHTML = `<td>${o.sessionId}</td><td>${o.profile}</td><td>${o.expiresAt||''}</td>`;
              tob.appendChild(tr);
            });
          }
          async function loadAudit(){
            const r = await fetch('/admin/audit/tail', {headers: headers()});
            if(!r.ok){ document.getElementById('audit').textContent='(no audit)'; return; }
            const jx = await r.json();
            document.getElementById('audit').textContent = jx.lines.map(l=>j(l)).join('\n');
          }
          refresh();
          </script>
        </body></html>
        """
        return HTMLResponse(html)

    @app.get('/admin/audit/tail')
    async def admin_audit_tail(request: Request, lines: int = 50):
        if not _admin_ok(request):
            return JSONResponse({'error':'unauthorized'}, status_code=401)
        import time
        log_dir = Path(os.environ.get('TSM_LOG_DIR', str(Path(__file__).resolve().parents[1] / 'logs')))
        date = time.strftime('%Y%m%d')
        fp = log_dir / f'policy-{date}.jsonl'
        out = []
        if fp.exists():
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    buf = f.readlines()[-int(max(1, min(500, lines))):]
                    for ln in buf:
                        ln = ln.strip()
                        if not ln:
                            continue
                        try:
                            out.append(json.loads(ln))
                        except Exception:
                            out.append({'raw': ln})
            except Exception:
                pass
        return JSONResponse({'lines': out})

    @app.get('/admin/new')
    async def admin_new(request: Request):
        if not _admin_ok(request):
            return HTMLResponse('<h1>Unauthorized</h1>', status_code=401)
        from urllib.parse import urlencode
        q = request.query_params
        pre_path = q.get('path') or ''
        pre_ttl = q.get('ttlSec') or '86400'
        html = f"""
        <!DOCTYPE html>
        <html><head><title>New Rule — Test-Start-MCP</title>
        <style>body{{font-family:sans-serif;padding:16px}} input,textarea{{width:100%}}</style>
        </head>
        <body>
          <h1>Add Allow Rule</h1>
          <form onsubmit="return addRule(event)">
            <label>Type
              <select id="type">
                <option value="path">path</option>
                <option value="scope">scope</option>
              </select>
            </label>
            <label>Path <input id="path" value="{pre_path}"/></label>
            <label>Scope Root <input id="scopeRoot" value=""/></label>
            <label>Patterns (comma) <input id="patterns" value="{Path(pre_path).name if pre_path else ''}"/></label>
            <label>Flags Allowed (comma) <input id="flagsAllowed" placeholder="--smoke,--no-tests"/></label>
            <label>TTL Seconds <input id="ttlSec" value="{pre_ttl}"/></label>
            <button type="submit">Add Rule</button>
          </form>
          <pre id="out">(no result)</pre>
          <script>
            function headers(){{
              const t = localStorage.getItem('TSM_ADMIN_TOKEN') || '';
              const h = {{'Content-Type':'application/json','Accept':'application/json'}};
              if (t) h['Authorization'] = 'Bearer '+t; return h;
            }}
            function j(o){{try{{return JSON.stringify(o,null,2)}}catch(e){{return String(o)}}}}
            async function addRule(ev){{ ev.preventDefault();
              const type = document.getElementById('type').value;
              const path = document.getElementById('path').value.trim();
              const scopeRoot = document.getElementById('scopeRoot').value.trim();
              const patterns = (document.getElementById('patterns').value||'').split(',').map(s=>s.trim()).filter(Boolean);
              const flagsAllowed = (document.getElementById('flagsAllowed').value||'').split(',').map(s=>s.trim()).filter(Boolean);
              const ttlSec = parseInt(document.getElementById('ttlSec').value||'0')||null;
              const body = {{type, path, scopeRoot, patterns, flagsAllowed, ttlSec}};
              const r = await fetch('/admin/allowlist/add', {{method:'POST', headers: headers(), body: JSON.stringify(body)}});
              document.getElementById('out').textContent = j(await r.json());
            }}
          </script>
        </body></html>
        """
        return HTMLResponse(html)

    @app.get('/admin/state')
    async def admin_state(request: Request):
        if not _admin_ok(request):
            return JSONResponse({'error':'unauthorized'}, status_code=401)
        fp = Path(os.environ.get('TSM_ALLOWED_FILE', str(Path(__file__).resolve().parents[1] / 'allowlist.json')))
        state = load_state(fp)
        return JSONResponse({'version': state.version, 'rules': [r.__dict__ for r in state.rules], 'overlays': [o.__dict__ for o in state.overlays], 'profiles': {k: {'caps': v.caps.__dict__ if v.caps else {}, 'flagsAllowed': v.flagsAllowed} for k, v in state.profiles.items()}})

    def _policy_audit(action: str, payload: Dict[str, Any], ok: bool) -> None:
        try:
            import time
            log_dir = Path(os.environ.get('TSM_LOG_DIR', str(Path(__file__).resolve().parents[1] / 'logs')))
            log_dir.mkdir(parents=True, exist_ok=True)
            date = time.strftime('%Y%m%d')
            fp = log_dir / f'policy-{date}.jsonl'
            line = {'ts': int(time.time()*1000), 'action': action, 'ok': bool(ok), 'payload': payload}
            with open(fp, 'a', encoding='utf-8') as f:
                f.write(json.dumps(line, ensure_ascii=False) + '\n')
        except Exception:
            pass

    @app.post('/admin/allowlist/add')
    async def admin_add(request: Request):
        if not _admin_ok(request):
            return JSONResponse({'error':'unauthorized'}, status_code=401)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({'ok': False, 'error': 'invalid json'}, status_code=400)
        rtype = (body.get('type') or 'path').strip()
        ttl_sec = body.get('ttlSec')
        flags_allowed = body.get('flagsAllowed') or []
        flags_denied = body.get('flagsDenied') or []
        caps = body.get('caps') or None
        # Resolve state
        state_fp = Path(os.environ.get('TSM_ALLOWED_FILE', str(Path(__file__).resolve().parents[1] / 'allowlist.json')))
        state = load_state(state_fp)
        allowed_root = Path(os.environ.get('TSM_ALLOWED_ROOT', str(Path(__file__).resolve().parents[1])))

        # Build rule
        from uuid import uuid4
        rule_id = f'rule-{uuid4().hex[:8]}'
        created_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
        expires_at = None
        if isinstance(ttl_sec, int) and ttl_sec > 0:
            expires_at = (__import__('datetime').datetime.now(__import__('datetime').timezone.utc) + __import__('datetime').timedelta(seconds=int(ttl_sec))).isoformat()

        if rtype == 'path':
            pth = body.get('path') or ''
            try:
                rp = Path(pth).resolve()
            except Exception:
                return JSONResponse({'ok': False, 'error': 'invalid path'}, status_code=400)
            if not rp.exists():
                return JSONResponse({'ok': False, 'error': 'path_not_found'}, status_code=400)
            if allowed_root.resolve() not in rp.parents and rp != allowed_root.resolve():
                return JSONResponse({'ok': False, 'error': 'outside_allowed_root'}, status_code=400)
            rule_obj = Rule(
                id=rule_id,
                type='path',
                path=str(rp),
                flagsAllowed=flags_allowed or None,
                flagsDenied=flags_denied or None,
                caps=Caps(**caps) if isinstance(caps, dict) else None,
                label=body.get('label'),
                note=body.get('note'),
                createdBy='admin',
                createdAt=created_at,
                expiresAt=expires_at,
            )
        elif rtype == 'scope':
            scope_root = body.get('scopeRoot') or ''
            patterns = body.get('patterns') or []
            try:
                rr = Path(scope_root).resolve()
            except Exception:
                return JSONResponse({'ok': False, 'error': 'invalid scopeRoot'}, status_code=400)
            if not rr.exists() or not rr.is_dir():
                return JSONResponse({'ok': False, 'error': 'scope_not_found'}, status_code=400)
            if allowed_root.resolve() not in rr.parents and rr != allowed_root.resolve():
                return JSONResponse({'ok': False, 'error': 'outside_allowed_root'}, status_code=400)
            if not patterns:
                return JSONResponse({'ok': False, 'error': 'patterns_required'}, status_code=400)
            rule_obj = Rule(
                id=rule_id,
                type='scope',
                scopeRoot=str(rr),
                patterns=list(patterns),
                flagsAllowed=flags_allowed or None,
                flagsDenied=flags_denied or None,
                caps=Caps(**caps) if isinstance(caps, dict) else None,
                label=body.get('label'),
                note=body.get('note'),
                createdBy='admin',
                createdAt=created_at,
                expiresAt=expires_at,
            )
        else:
            return JSONResponse({'ok': False, 'error': 'invalid type'}, status_code=400)

        # Persist
        try:
            state.rules.append(rule_obj)
            save_state(state_fp, state)
            _policy_audit('allowlist/add', rule_obj.__dict__, True)
            return JSONResponse({'ok': True, 'rule': rule_obj.__dict__})
        except Exception as e:
            _policy_audit('allowlist/add', {'rule': getattr(rule_obj, '__dict__', {}), 'error': str(e)}, False)
            return JSONResponse({'ok': False, 'error': 'persist_failed'}, status_code=500)

    @app.post('/admin/allowlist/remove')
    async def admin_remove(request: Request):
        if not _admin_ok(request):
            return JSONResponse({'error':'unauthorized'}, status_code=401)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({'ok': False, 'error': 'invalid json'}, status_code=400)
        rid = body.get('id')
        if not rid:
            return JSONResponse({'ok': False, 'error': 'id_required'}, status_code=400)
        state_fp = Path(os.environ.get('TSM_ALLOWED_FILE', str(Path(__file__).resolve().parents[1] / 'allowlist.json')))
        st = load_state(state_fp)
        before = len(st.rules)
        st.rules = [r for r in st.rules if getattr(r, 'id', None) != rid]
        after = len(st.rules)
        # Persist
        try:
            state_dict = {
                'version': st.version,
                'rules': [r.__dict__ for r in st.rules],
                'overlays': [o.__dict__ for o in st.overlays],
                'profiles': {k: {'caps': v.caps.__dict__ if v.caps else {}, 'flagsAllowed': v.flagsAllowed} for k, v in st.profiles.items()},
            }
            state_fp.parent.mkdir(parents=True, exist_ok=True)
            state_fp.write_text(json.dumps(state_dict, ensure_ascii=False, indent=2), encoding='utf-8')
            removed = before - after
            _policy_audit('allowlist/remove', {'id': rid, 'removed': removed}, True)
            return JSONResponse({'ok': True, 'removed': removed})
        except Exception as e:
            _policy_audit('allowlist/remove', {'id': rid, 'error': str(e)}, False)
            return JSONResponse({'ok': False, 'error': 'persist_failed'}, status_code=500)

    @app.post('/admin/session/profile')
    async def admin_session_profile(request: Request):
        if not _admin_ok(request):
            return JSONResponse({'error':'unauthorized'}, status_code=401)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({'ok': False, 'error': 'invalid json'}, status_code=400)
        session_id = body.get('sessionId')
        profile = body.get('profile')
        ttl_sec = body.get('ttlSec') or 3600
        if not session_id or not profile:
            return JSONResponse({'ok': False, 'error': 'sessionId_and_profile_required'}, status_code=400)
        state_fp = Path(os.environ.get('TSM_ALLOWED_FILE', str(Path(__file__).resolve().parents[1] / 'allowlist.json')))
        st = load_state(state_fp)
        if profile not in (st.profiles or {}):
            return JSONResponse({'ok': False, 'error': 'unknown_profile'}, status_code=400)
        # compute expiresAt
        import datetime as _dt
        exp = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=int(ttl_sec))).isoformat()
        # Replace or add overlay for session
        st.overlays = [o for o in st.overlays if o.sessionId != session_id]
        st.overlays.append(Overlay(sessionId=session_id, profile=profile, expiresAt=exp))
        try:
            save_state(state_fp, st)
            _policy_audit('session/profile', {'sessionId': session_id, 'profile': profile, 'expiresAt': exp}, True)
            return JSONResponse({'ok': True, 'overlay': {'sessionId': session_id, 'profile': profile, 'expiresAt': exp}})
        except Exception as e:
            _policy_audit('session/profile', {'sessionId': session_id, 'profile': profile, 'error': str(e)}, False)
            return JSONResponse({'ok': False, 'error': 'persist_failed'}, status_code=500)

    @app.post('/admin/reload')
    async def admin_reload(request: Request):
        if not _admin_ok(request):
            return JSONResponse({'error':'unauthorized'}, status_code=401)
        # For now, load_state on demand by callers (stateless). Stub 200.
        return JSONResponse({'ok': True})

    return app


def main():
    p = argparse.ArgumentParser(description='Test-Start-MCP')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=7060)
    args = p.parse_args()
    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
