#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
import logging
from pathlib import Path
from typing import List

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, HTMLResponse
    import uvicorn
except Exception as e:
    print("Missing dependencies: fastapi, uvicorn")
    print("Create a venv and: pip install fastapi uvicorn")
    raise SystemExit(1)


def connect_db(home: Path) -> sqlite3.Connection:
    db = home / 'index.sqlite'
    if not db.exists():
        print(f"Warning: index not found at {db}. Run indexer/build_index.py first.")
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    return con


def create_app(home: Path) -> FastAPI:
    app = FastAPI()
    con = connect_db(home)
    # Basic logging and optional file logging
    lvl = os.environ.get('PRIOR_LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(level=getattr(logging, lvl, logging.INFO), format='[%(levelname)s] %(message)s')
    LOG = logging.getLogger('prior-self-mcp')
    log_dir = os.environ.get('PRIOR_LOG_DIR')
    log_file = os.environ.get('PRIOR_LOG_FILE')
    ts_flag = os.environ.get('PRIOR_LOG_TS', '0') in ('1','true','TRUE')
    rotate_bytes = os.environ.get('PRIOR_LOG_ROTATE')
    rotate_backups = int(os.environ.get('PRIOR_LOG_BACKUPS', '5'))
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

    def _auth_ok(request: Request) -> bool:
        token = os.environ.get('PRIOR_TOKEN') or os.environ.get('PRIOR_SELF_TOKEN')
        if not token:
            return True
        hdr = request.headers.get('Authorization')
        if not hdr or not hdr.startswith('Bearer '):
            return False
        return hdr.split(' ', 1)[1].strip() == token.strip()

    @app.get('/healthz')
    def healthz():
        return {'ok': True}

    @app.post('/actions/search_previous_chats')
    async def search_previous_chats(req: Request):
        if not _auth_ok(req):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        body = await req.json()
        query = body.get('query') or ''
        project = body.get('project')
        k = int(body.get('k', 10))
        sql = "SELECT chat_id, ts, substr(text,1,200) as excerpt FROM messages WHERE fts_messages MATCH ?"
        args: List[str] = [query]
        if project:
            sql = sql + " AND project = ?"  # simple filter
            args.append(project)
        sql += " ORDER BY ts DESC LIMIT ?"
        args.append(str(k))
        cur = con.execute(sql, args)
        items = [dict(row) for row in cur.fetchall()]
        return JSONResponse({'items': items})

    @app.post('/actions/get_chat_context')
    async def get_chat_context(req: Request):
        if not _auth_ok(req):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        body = await req.json()
        chat_id = body.get('chat_id')
        if not chat_id:
            return JSONResponse({'error': 'missing chat_id'}, status_code=400)
        cur = con.execute(
            "SELECT ts, role, text FROM messages WHERE chat_id = ? ORDER BY ts ASC",
            (chat_id,),
        )
        msgs = [dict(row) for row in cur.fetchall()]
        return JSONResponse({'messages': msgs})

    @app.post('/actions/list_sessions')
    async def list_sessions(req: Request):
        if not _auth_ok(req):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        body = await req.json()
        project = body.get('project')
        if project:
            cur = con.execute(
                "SELECT chat_id, MIN(ts) as first_ts, MAX(ts) as last_ts, COUNT(*) as message_count FROM messages WHERE project = ? GROUP BY chat_id ORDER BY last_ts DESC",
                (project,),
            )
        else:
            cur = con.execute(
                "SELECT chat_id, MIN(ts) as first_ts, MAX(ts) as last_ts, COUNT(*) as message_count FROM messages GROUP BY chat_id ORDER BY last_ts DESC"
            )
        items = [dict(row) for row in cur.fetchall()]
        return JSONResponse({'sessions': items})

    @app.post('/actions/summarize_decisions')
    async def summarize_decisions(req: Request):
        if not _auth_ok(req):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        body = await req.json()
        chat_id = body.get('chat_id')
        # Minimal placeholder (decisions table out of scope for v1)
        return JSONResponse({'decisions': [], 'note': 'decision extraction TBD'})

    @app.get('/mcp_ui')
    async def mcp_ui():
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
          <title>Prior‑Self MCP UI</title>
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
          <h1>Prior‑Self — MCP UI</h1>
          <small>Authorization uses PRIOR_TOKEN from localStorage if set.</small>
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
            <label>Tool name <input id="tname" value="search_previous_chats"/></label>
            <label>Arguments (JSON)
              <textarea id="targs" rows="6">{
  "query": "tokens",
  "project": "RoadNerd",
  "k": 5
}</textarea></label>
            <button onclick="callTool()">tools/call</button>
            <pre id="callOut">(no call)</pre>
          </section>
          <script>
            function headers(){
              const t = localStorage.getItem('PRIOR_TOKEN') || '';
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
    def mcp_tools():
        return [
            {
                'name': 'search_previous_chats',
                'title': 'Search Previous Chats',
                'description': 'Search FTS index for prior messages.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string'},
                        'project': {'type': ['string','null']},
                        'k': {'type': 'integer', 'default': 10, 'minimum': 1, 'maximum': 200}
                    },
                    'required': ['query']
                },
                'outputSchema': {
                    'type': 'object',
                    'properties': {'items': {'type': 'array', 'items': {'type': 'object'}}},
                    'required': ['items']
                }
            },
            {
                'name': 'get_chat_context',
                'title': 'Get Chat Context',
                'description': 'Return messages for a chat_id ordered by time.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {'chat_id': {'type': 'string'}},
                    'required': ['chat_id']
                },
                'outputSchema': {
                    'type': 'object',
                    'properties': {'messages': {'type': 'array', 'items': {'type': 'object'}}},
                    'required': ['messages']
                }
            },
            {
                'name': 'list_sessions',
                'title': 'List Sessions',
                'description': 'List sessions, optionally filtered by project.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {'project': {'type': ['string','null']}}
                },
                'outputSchema': {
                    'type': 'object',
                    'properties': {'sessions': {'type': 'array', 'items': {'type': 'object'}}},
                    'required': ['sessions']
                }
            },
            {
                'name': 'summarize_decisions',
                'title': 'Summarize Decisions',
                'description': 'Placeholder decision extraction for a chat_id (TBD).',
                'inputSchema': {
                    'type': 'object',
                    'properties': {'chat_id': {'type': 'string'}},
                    'required': []
                },
                'outputSchema': {
                    'type': 'object',
                    'properties': {'decisions': {'type': 'array', 'items': {'type': 'object'}}, 'note': {'type': 'string'}}
                }
            },
        ]

    def _mcp_response(id_value, result=None, error=None):
        if error is not None:
            return {'jsonrpc': '2.0', 'id': id_value, 'error': error}
        return {'jsonrpc': '2.0', 'id': id_value, 'result': result}

    def _text_and_structured(obj):
        return {'content': [{'type': 'text', 'text': json.dumps(obj, ensure_ascii=False)}], 'structuredContent': obj, 'isError': False}

    @app.post('/mcp')
    async def mcp(req: Request):
        if not _auth_ok(req):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        try:
            body = await req.json()
        except Exception:
            return JSONResponse({'error': 'invalid json'}, status_code=400)

        async def handle_one(m):
            if not isinstance(m, dict):
                return None
            msg_id = m.get('id')
            method = m.get('method')
            params = m.get('params') or {}

            if method == 'initialize':
                return _mcp_response(msg_id, result={
                    'protocolVersion': '2025-06-18',
                    'capabilities': {'tools': {'listChanged': False}},
                    'serverInfo': {'name': 'Prior-Self', 'title': 'Prior-Self MCP', 'version': '0.1.0'},
                })

            if method == 'tools/list':
                return _mcp_response(msg_id, result={'tools': mcp_tools()})

            if method == 'tools/call':
                name = (params or {}).get('name')
                arguments = (params or {}).get('arguments') or {}
                try:
                    if name == 'search_previous_chats':
                        query = arguments.get('query') or ''
                        project = arguments.get('project')
                        k = int(arguments.get('k') or 10)
                        sql = "SELECT chat_id, ts, substr(text,1,200) as excerpt FROM messages WHERE fts_messages MATCH ?"
                        args: List[str] = [query]
                        if project:
                            sql = sql + " AND project = ?"
                            args.append(project)
                        sql += " ORDER BY ts DESC LIMIT ?"
                        args.append(str(k))
                        cur = con.execute(sql, args)
                        items = [dict(row) for row in cur.fetchall()]
                        return _mcp_response(msg_id, result=_text_and_structured({'items': items}))
                    elif name == 'get_chat_context':
                        chat_id = arguments.get('chat_id')
                        if not chat_id:
                            return _mcp_response(msg_id, result={'content':[{'type':'text','text':'Error: missing chat_id'}], 'structuredContent': {'error': {'message': 'missing chat_id'}}, 'isError': True})
                        cur = con.execute("SELECT ts, role, text FROM messages WHERE chat_id = ? ORDER BY ts ASC", (chat_id,))
                        msgs = [dict(row) for row in cur.fetchall()]
                        return _mcp_response(msg_id, result=_text_and_structured({'messages': msgs}))
                    elif name == 'list_sessions':
                        project = arguments.get('project')
                        if project:
                            cur = con.execute("SELECT chat_id, MIN(ts) as first_ts, MAX(ts) as last_ts, COUNT(*) as message_count FROM messages WHERE project = ? GROUP BY chat_id ORDER BY last_ts DESC", (project,))
                        else:
                            cur = con.execute("SELECT chat_id, MIN(ts) as first_ts, MAX(ts) as last_ts, COUNT(*) as message_count FROM messages GROUP BY chat_id ORDER BY last_ts DESC")
                        items = [dict(row) for row in cur.fetchall()]
                        return _mcp_response(msg_id, result=_text_and_structured({'sessions': items}))
                    elif name == 'summarize_decisions':
                        return _mcp_response(msg_id, result=_text_and_structured({'decisions': [], 'note': 'decision extraction TBD'}))
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

    return app


def main():
    ap = argparse.ArgumentParser(description='Prior-Self MCP HTTP Server')
    ap.add_argument('--home', default=os.environ.get('PRIOR_SELF_HOME', os.path.expanduser('~/.roadnerd/chatdb')))
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=7070)
    args = ap.parse_args()

    home = Path(args.home)
    home.mkdir(parents=True, exist_ok=True)
    app = create_app(home)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
