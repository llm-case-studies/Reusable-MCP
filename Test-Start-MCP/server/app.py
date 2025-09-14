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


def create_app() -> FastAPI:
    app = FastAPI()

    # Basic logging; TSM_LOG_LEVEL=DEBUG|INFO|WARNING
    lvl = os.environ.get('TSM_LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(level=getattr(logging, lvl, logging.INFO), format='[%(levelname)s] %(message)s')
    LOG = logging.getLogger('test-start-mcp')

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
        ok, err, prep = validate_and_prepare(path, args, env, timeout_ms)
        if not ok:
            return JSONResponse({'error': err.get('code', 'error'), 'message': err.get('message')}, status_code=400 if err.get('code') != 'E_FORBIDDEN' else 403)
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
                if args.strip().startswith('['):
                    parsed_args = list(json.loads(args))
                else:
                    parsed_args = [s for s in (args.split(',')) if s != '']
            except Exception:
                return JSONResponse({'error': 'E_BAD_ARG', 'message': 'args must be JSON array or comma-separated string'}, status_code=400)
        ok, err, prep = validate_and_prepare(path, parsed_args, {}, timeout_ms)
        if not ok:
            return JSONResponse({'error': err.get('code', 'error'), 'message': err.get('message')}, status_code=400 if err.get('code') != 'E_FORBIDDEN' else 403)

        def gen():
            try:
                for ev in stream_process(prep):
                    yield f"event: {ev['event']}\n" + f"data: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"event: error\n" + f"data: {json.dumps({'code': 'E_EXEC', 'message': str(e)})}\n\n"

        return StreamingResponse(gen(), media_type='text/event-stream')

    # ---- MCP JSON-RPC endpoint ----
    def mcp_tools() -> List[Dict[str, Any]]:
        return tool_schemas()

    def _mcp_response(id_value, result=None, error=None):
        if error is not None:
            return {'jsonrpc': '2.0', 'id': id_value, 'error': error}
        return {'jsonrpc': '2.0', 'id': id_value, 'result': result}

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
                return _mcp_response(msg_id, result={
                    'protocolVersion': PROTOCOL_VERSION,
                    'capabilities': {'tools': {}},
                    'serverInfo': {'name': 'Test-Start-MCP', 'version': PROTOCOL_VERSION},
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
                        ok, err, prep = validate_and_prepare(path, args, env, timeout_ms)
                        if not ok:
                            return _mcp_response(msg_id, result={'content': [{'type': 'text', 'text': err.get('message', 'error')}], 'structuredContent': {'error': err}, 'isError': True})
                        res = run_sync(prep)
                        return _mcp_response(msg_id, result={'content': [{'type': 'text', 'text': f"exit {res['exitCode']} ({res['duration_ms']}ms)"}], 'structuredContent': res, 'isError': False})
                    if name == 'list_allowed':
                        scripts = list_allowed_scripts()
                        return _mcp_response(msg_id, result={'content': [{'type': 'text', 'text': f"{len(scripts)} scripts"}], 'structuredContent': {'scripts': scripts}})
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
            return JSONResponse(out)
        elif isinstance(body, dict):
            resp = await handle_one(body)
            if resp is None:
                return JSONResponse(status_code=202, content=None)
            return JSONResponse(resp)
        else:
            return JSONResponse({'error': 'invalid payload'}, status_code=400)

    @app.get('/mcp_ui')
    async def mcp_ui():
        html = '''
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
              <textarea id="targs" rows="6">{
  "path": "/bin/echo",
  "args": ["hello"]
}</textarea></label>
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
        '''
        return HTMLResponse(content=html)

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
