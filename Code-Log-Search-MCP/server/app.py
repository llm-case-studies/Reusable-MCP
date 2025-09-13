#!/usr/bin/env python3
import argparse
import json
import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
    import uvicorn
except Exception:
    print("Missing dependencies: fastapi, uvicorn")
    print("Create a venv and: pip install fastapi uvicorn")
    raise SystemExit(1)

try:
    # When run as a module (python -m server.app)
    from .search import perform_code_search, perform_logs_search
except Exception:
    # When run as a script (python server/app.py)
    from server.search import perform_code_search, perform_logs_search


def _auth_ok(request: Request) -> bool:
    token = os.environ.get('CLS_TOKEN')
    if not token:
        return True
    hdr = request.headers.get('Authorization')
    if not hdr or not hdr.startswith('Bearer '):
        return False
    return hdr.split(' ', 1)[1].strip() == token.strip()


def create_app(default_code_root: Path, logs_root: Path) -> FastAPI:
    app = FastAPI()
    # Basic logging (stdout). Control with CLS_LOG_LEVEL (e.g., DEBUG, INFO, WARNING).
    lvl = os.environ.get('CLS_LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(level=getattr(logging, lvl, logging.INFO), format='[%(levelname)s] %(message)s')
    LOG = logging.getLogger('code-log-search-mcp')
    # Optional file logging controls:
    #   CLS_LOG_DIR: directory for logs (default none)
    #   CLS_LOG_FILE: explicit file path (overrides CLS_LOG_DIR)
    #   CLS_LOG_TS: if set truthy, include timestamp in filename when using CLS_LOG_DIR
    #   CLS_LOG_ROTATE: if set, enable RotatingFileHandler (bytes, default 5242880). CLS_LOG_BACKUPS (default 5)
    log_dir = os.environ.get('CLS_LOG_DIR')
    log_file = os.environ.get('CLS_LOG_FILE')
    ts_flag = os.environ.get('CLS_LOG_TS', '0') in ('1', 'true', 'TRUE')
    rotate_bytes = os.environ.get('CLS_LOG_ROTATE')
    rotate_backups = int(os.environ.get('CLS_LOG_BACKUPS', '5'))
    try:
        if log_dir and not log_file:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            if ts_flag:
                from datetime import datetime
                ts = datetime.now().strftime('%Y%m%d-%H%M%S')
                log_file = str(Path(log_dir) / f'app-{ts}.log')
            else:
                log_file = str(Path(log_dir) / 'app.log')
        if log_file:
            if rotate_bytes:
                from logging.handlers import RotatingFileHandler
                max_bytes = int(rotate_bytes) if str(rotate_bytes).isdigit() else 5 * 1024 * 1024
                fh = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=rotate_backups)
            else:
                fh = logging.FileHandler(log_file)
            fh.setLevel(getattr(logging, lvl, logging.INFO))
            fh.setFormatter(logging.Formatter('[%(levelname)s] %(asctime)s %(message)s'))
            logging.getLogger().addHandler(fh)
            LOG.info('File logging enabled at %s', log_file)
    except Exception as e:
        LOG.warning('Failed to initialize file logging: %s', e)

    @app.get('/healthz')
    def healthz():
        return {'ok': True, 'code_root': str(default_code_root), 'logs_root': str(logs_root)}

    @app.post('/actions/search_code')
    async def search_code(req: Request):
        if not _auth_ok(req):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        body = await req.json()
        query = body.get('query') or ''
        root_in = body.get('root')
        root_path = _sanitize_root(root_in)
        if root_path is None:
            return JSONResponse({'error': 'forbidden_root', 'message': 'root must be within default_code_root'}, status_code=400)
        globs = body.get('globs') or []
        max_results = int(body.get('maxResults', 100))
        context_lines = int(body.get('contextLines', 0))
        literal = bool(body.get('literal', False))
        timeout_ms = body.get('timeoutMs')
        LOG.debug('search_code query=%r root=%s max=%d ctx=%d literal=%s timeoutMs=%s', query, root_path, max_results, context_lines, literal, timeout_ms)
        hits = perform_code_search(query, root_path, globs, max_results, context_lines, literal=literal, timeout_ms=timeout_ms)
        return JSONResponse({'hits': [h.__dict__ for h in hits]})

    @app.get('/sse/search_code_stream')
    async def search_code_stream(request: Request, query: str, root: Optional[str] = None, maxResults: int = 200, durationSec: int = 20):
        if not _auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        rp = _sanitize_root(root or str(default_code_root))
        if rp is None:
            return JSONResponse({'error': 'forbidden_root', 'message': 'root must be within default_code_root'}, status_code=400)

        def event_stream():
            try:
                import time
                start = time.time()
                sent = 0
                last_ping = 0.0
                hits = perform_code_search(query, rp, None, maxResults, 0, literal=False, timeout_ms=int(durationSec * 1000))
                for h in hits:
                    # Heartbeat
                    now = time.time()
                    if now - last_ping > 5.0:
                        yield "event: ping\n" + f"data: {{\"t\": {int(now)} }}\n\n"
                        last_ping = now
                    yield f"event: message\n" + f"data: {json.dumps(h.__dict__, ensure_ascii=False)}\n\n"
                    sent += 1
                    if sent >= maxResults or (now - start) >= durationSec:
                        break
                yield f"event: end\n" + f"data: {json.dumps({'count': sent})}\n\n"
            except Exception as e:
                yield f"event: error\n" + f"data: {json.dumps({'error': str(e)})}\n\n"
        return StreamingResponse(event_stream(), media_type='text/event-stream')

    @app.post('/actions/search_logs')
    async def search_logs(req: Request):
        if not _auth_ok(req):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        body = await req.json()
        query = body.get('query') or ''
        date = body.get('date')
        mode = body.get('mode')
        max_results = int(body.get('maxResults', 200))
        LOG.debug('search_logs query=%r date=%r mode=%r max=%d', query, date, mode, max_results)
        results = perform_logs_search(query, logs_root, date=date, mode=mode, max_results=max_results)
        return JSONResponse({'entries': results})

    @app.get('/mcp_ui')
    async def mcp_ui():
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
          <title>Code-Log-Search MCP UI</title>
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
          <h1>Code‑Log‑Search — MCP UI</h1>
          <small>Authorization uses CLS_TOKEN from localStorage if set.</small>
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
            <label>Tool name <input id="tname" value="search_code"/></label>
            <label>Arguments (JSON)
              <textarea id="targs" rows="6">{
  "query": "TODO|FIXME",
  "root": "/home/you/Projects/repo",
  "maxResults": 10,
  "contextLines": 0
}</textarea></label>
            <button onclick="callTool()">tools/call</button>
            <pre id="callOut">(no call)</pre>
          </section>
          <script>
            function headers(){
              const t = localStorage.getItem('CLS_TOKEN') || '';
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

    # ---- MCP Streamable HTTP endpoint ----
    def mcp_tools() -> List[Dict[str, Any]]:
        return [
            {
                'name': 'search_code',
                'title': 'Search Code',
                'description': 'Ripgrep-based code search under a root with optional globs and context.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string'},
                        'root': {'type': ['string','null'], 'description': 'Root directory; defaults to server default.'},
                        'globs': {'type': 'array', 'items': {'type': 'string'}},
                        'maxResults': {'type': 'integer', 'default': 100, 'minimum': 1, 'maximum': 2000},
                        'contextLines': {'type': 'integer', 'default': 0, 'minimum': 0, 'maximum': 20},
                        'literal': {'type': 'boolean', 'default': False, 'description': 'Use fixed-string matching (rg -F) instead of regex.'},
                        'timeoutMs': {'type': 'integer', 'default': 3000, 'minimum': 100, 'maximum': 60000, 'description': 'Max runtime before aborting rg.'},
                    },
                    'required': ['query']
                },
                'outputSchema': {
                    'type': 'object',
                    'properties': {
                        'hits': {'type': 'array', 'items': {'type': 'object'}}
                    },
                    'required': ['hits']
                }
            },
            {
                'name': 'search_logs',
                'title': 'Search Logs',
                'description': 'Search RoadNerd JSONL logs under logs_root by query/date/mode.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string'},
                        'date': {'type': ['string','null'], 'description': 'YYYYMMDD file name stem'},
                        'mode': {'type': ['string','null'], 'description': 'Optional mode filter (e.g., brainstorm).'},
                        'maxResults': {'type': 'integer', 'default': 200, 'minimum': 1, 'maximum': 10000}
                    },
                    'required': ['query']
                },
                'outputSchema': {
                    'type': 'object',
                    'properties': {
                        'entries': {'type': 'array', 'items': {'type': 'object'}}
                    },
                    'required': ['entries']
                }
            },
        ]

    def _mcp_response(id_value, result=None, error=None):
        if error is not None:
            return {'jsonrpc': '2.0', 'id': id_value, 'error': error}
        return {'jsonrpc': '2.0', 'id': id_value, 'result': result}

    def _text_and_structured(obj: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'content': [{'type': 'text', 'text': json.dumps(obj, ensure_ascii=False)}],
            'structuredContent': obj,
            'isError': False,
        }

    @app.post('/mcp')
    async def mcp(req: Request):
        if not _auth_ok(req):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)

        try:
            body = await req.json()
        except Exception:
            return JSONResponse({'error': 'invalid json'}, status_code=400)

        async def handle_one(msg: Dict[str, Any]):
            if not isinstance(msg, dict):
                return None
            msg_id = msg.get('id')
            method = msg.get('method')
            params = msg.get('params') or {}

            if method == 'initialize':
                return _mcp_response(msg_id, result={
                    'protocolVersion': '2025-06-18',
                    'capabilities': {'tools': {'listChanged': False}},
                    'serverInfo': {'name': 'Code-Log-Search', 'title': 'Code+Log Search MCP', 'version': '0.1.0'},
                })

            if method == 'tools/list':
                return _mcp_response(msg_id, result={'tools': mcp_tools()})

            if method == 'tools/call':
                name = (params or {}).get('name')
                arguments = (params or {}).get('arguments') or {}
                try:
                    if name == 'search_code':
                        q = arguments.get('query') or ''
                        root_in = arguments.get('root') or str(default_code_root)
                        root_sanitized = _sanitize_root(root_in)
                        if root_sanitized is None:
                            return _mcp_response(msg_id, result={'content':[{'type':'text','text':'Error: forbidden_root'}], 'structuredContent': {'error': {'message': 'forbidden_root'}}, 'isError': True})
                        globs = arguments.get('globs') or []
                        max_results = int(arguments.get('maxResults') or 100)
                        context_lines = int(arguments.get('contextLines') or 0)
                        literal = bool(arguments.get('literal') or False)
                        timeout_ms = arguments.get('timeoutMs')
                        LOG.debug('mcp tools/call search_code q=%r root=%s max=%d ctx=%d literal=%s timeoutMs=%s', q, root_sanitized, max_results, context_lines, literal, timeout_ms)
                        hits = perform_code_search(q, root_sanitized, globs, max_results, context_lines, literal=literal, timeout_ms=timeout_ms)
                        return _mcp_response(msg_id, result=_text_and_structured({'hits': [h.__dict__ for h in hits]}))
                    elif name == 'search_logs':
                        q = arguments.get('query') or ''
                        date = arguments.get('date')
                        mode = arguments.get('mode')
                        max_results = int(arguments.get('maxResults') or 200)
                        LOG.debug('mcp tools/call search_logs q=%r date=%r mode=%r max=%d', q, date, mode, max_results)
                        entries = perform_logs_search(q, logs_root, date=date, mode=mode, max_results=max_results)
                        return _mcp_response(msg_id, result=_text_and_structured({'entries': entries}))
                    else:
                        return _mcp_response(msg_id, error={'code': -32602, 'message': f'Unknown tool: {name}'})
                except Exception as e:
                    return _mcp_response(msg_id, result={'content':[{'type':'text','text':f'Error: {e}'}], 'structuredContent': {'error': {'message': str(e)}}, 'isError': True})

            return _mcp_response(msg_id, error={'code': -32601, 'message': f'Unknown method: {method}'})

        if isinstance(body, list):
            out = []
            for m in body:
                r = await handle_one(m)
                if r is not None:
                    out.append(r)
            return JSONResponse(out) if out else JSONResponse(status_code=202, content=None)
        elif isinstance(body, dict):
            r = await handle_one(body)
            return JSONResponse(r) if r is not None else JSONResponse(status_code=202, content=None)
        return JSONResponse({'error': 'invalid payload'}, status_code=400)

    @app.get('/search')
    async def search_ui():
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
          <title>Code+Log Search</title>
          <style>
            body {{ font-family: system-ui, sans-serif; background: #0b1220; color: #e0e6f0; padding: 20px; }}
            section {{ background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
            label {{ display: block; margin: 6px 0; }}
            input, textarea {{ width: 100%; background: #0b1220; color: #e0e6f0; border: 1px solid #374151; border-radius: 6px; padding: 8px; }}
            button {{ background: #2563eb; color: white; border: 0; border-radius: 6px; padding: 8px 12px; cursor: pointer; margin-right: 6px; }}
            pre {{ background: #0b1220; border: 1px solid #1f2937; border-radius: 8px; padding: 10px; max-height: 50vh; overflow: auto; }}
          </style>
        </head>
        <body>
          <h1>Code + Log Search MCP</h1>
          <section>
            <h2>Code Search</h2>
            <label>Query <input id="q" placeholder="e.g., num_predict"/></label>
            <label>Root <input id="root" value="{str(default_code_root)}"/></label>
            <label>Globs (comma-separated) <input id="globs" placeholder="e.g., *.py,*.md"/></label>
            <label>maxResults <input id="maxResults" value="100"/></label>
            <label>contextLines <input id="contextLines" value="0"/></label>
            <button onclick="codeSearch()">Search</button>
            <button onclick="codeStream()">Stream</button>
            <pre id="codeOut">(no results)</pre>
          </section>
          <section>
            <h2>Log Search</h2>
            <label>Query <input id="lq" placeholder="e.g., brainstorm"/></label>
            <label>Date (YYYYMMDD, optional) <input id="ldate"/></label>
            <label>Mode (optional) <input id="lmode" placeholder="brainstorm|probe|judge|legacy"/></label>
            <label>maxResults <input id="lmax" value="200"/></label>
            <button onclick="logSearch()">Search Logs</button>
            <pre id="logOut">(no results)</pre>
          </section>
          <script>
            function j(o){{return JSON.stringify(o,null,2);}}
            async function codeSearch(){{
              const body={{
                query:document.getElementById('q').value,
                root:document.getElementById('root').value,
                maxResults:parseInt(document.getElementById('maxResults').value||'100'),
                contextLines:parseInt(document.getElementById('contextLines').value||'0')
              }};
              const globs=document.getElementById('globs').value.trim();
              if(globs) body.globs=globs.split(',').map(s=>s.trim()).filter(Boolean);
              const r=await fetch('/actions/search_code',{{method:'POST',headers:headers(),body:JSON.stringify(body)}});
              document.getElementById('codeOut').textContent=j(await r.json());
            }}
            function codeStream(){{
              const q=document.getElementById('q').value; const root=document.getElementById('root').value; const out=document.getElementById('codeOut'); out.textContent='';
              const es=new EventSource('/sse/search_code_stream?query='+encodeURIComponent(q)+'&root='+encodeURIComponent(root));
              es.onmessage=(e)=>{{ out.textContent += e.data+'\n'; }};
              es.addEventListener('end',(e)=>{{ out.textContent += '\n[END] '+e.data; es.close(); }});
              es.addEventListener('error',(e)=>{{ out.textContent += '\n[ERROR]'; es.close(); }});
            }}
            async function logSearch(){{
              const body={{query:document.getElementById('lq').value}};
              const d=document.getElementById('ldate').value.trim(); if(d) body.date=d;
              const m=document.getElementById('lmode').value.trim(); if(m) body.mode=m;
              body.maxResults=parseInt(document.getElementById('lmax').value||'200');
              const r=await fetch('/actions/search_logs',{{method:'POST',headers:headers(),body:JSON.stringify(body)}});
              document.getElementById('logOut').textContent=j(await r.json());
            }}
            function headers(){{
              const t = localStorage.getItem('CLS_TOKEN') || '';
              const h = {{'Content-Type':'application/json'}};
              if (t) h['Authorization'] = 'Bearer '+t;
              return h;
            }}
          </script>
        </body>
        </html>
        '''
        return html

    return app


def main():
    ap = argparse.ArgumentParser(description='Code-Log-Search-MCP HTTP/SSE Server')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=7080)
    ap.add_argument('--default-code-root', default=os.environ.get('CLS_CODE_ROOT', os.getcwd()))
    ap.add_argument('--logs-root', default=os.environ.get('RN_LOG_DIR', os.path.expanduser('~/\.roadnerd/logs')))
    allowed_root = default_code_root.resolve()

    def _sanitize_root(requested: Optional[str]) -> Optional[Path]:
        if not requested:
            return allowed_root
        try:
            rp = Path(requested).resolve()
        except Exception:
            return None
        try:
            # Python 3.9+: use is_relative_to when available
            if hasattr(rp, 'is_relative_to'):
                if rp.is_relative_to(allowed_root):
                    return rp
                return None
            # Fallback: raise if not relative
            rp.relative_to(allowed_root)
            return rp
        except Exception:
            return None
    args = ap.parse_args()

    default_code_root = Path(args.default_code_root)
    logs_root = Path(args.logs_root)
    logs_root.mkdir(parents=True, exist_ok=True)
    app = create_app(default_code_root, logs_root)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
