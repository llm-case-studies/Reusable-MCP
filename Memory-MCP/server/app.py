#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, StreamingResponse
    import uvicorn
except Exception:
    print("Missing dependencies: fastapi, uvicorn")
    print("Create a venv and: pip install fastapi uvicorn")
    raise SystemExit(1)

from .storage import init_db, write_memory, read_memory, search_memory, list_memories


def _auth_ok(request: Request) -> bool:
    token = os.environ.get('MEM_TOKEN')
    if not token:
        return True
    hdr = request.headers.get('Authorization')
    if not hdr or not hdr.startswith('Bearer '):
        return False
    return hdr.split(' ', 1)[1].strip() == token.strip()


def create_app(home: Path) -> FastAPI:
    app = FastAPI()
    con = init_db(home)

    @app.get('/healthz')
    def healthz():
        return {'ok': True, 'home': str(home)}

    @app.post('/actions/write_memory')
    async def http_write_memory(req: Request):
        if not _auth_ok(req):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        body = await req.json()
        project = body.get('project')
        scope = body.get('scope') or 'project'
        key = body.get('key')
        text = body.get('text') or ''
        tags = body.get('tags') or []
        ttl_sec = body.get('ttlSec')
        metadata = body.get('metadata')
        entry = write_memory(con, home, project=project, scope=scope, key=key, text=text, tags=tags, ttl_sec=ttl_sec, metadata=metadata)
        return JSONResponse(entry.__dict__)

    @app.post('/actions/read_memory')
    async def http_read_memory(req: Request):
        if not _auth_ok(req):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        body = await req.json()
        eid = body.get('id')
        project = body.get('project')
        key = body.get('key')
        entry = read_memory(con, id=eid, project=project, key=key)
        return JSONResponse({'entry': entry.__dict__ if entry else None})

    @app.post('/actions/search_memory')
    async def http_search_memory(req: Request):
        if not _auth_ok(req):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        body = await req.json()
        query = body.get('query') or ''
        project = body.get('project')
        tags = body.get('tags') or []
        k = int(body.get('k', 20))
        items = search_memory(con, query=query, project=project, tags=tags, k=k)
        return JSONResponse({'items': [e.__dict__ for e in items]})

    @app.post('/actions/list_memories')
    async def http_list_memories(req: Request):
        if not _auth_ok(req):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        body = await req.json()
        project = body.get('project')
        tags = body.get('tags') or []
        limit = int(body.get('limit', 50))
        offset = int(body.get('offset', 0))
        items = list_memories(con, project=project, tags=tags, limit=limit, offset=offset)
        return JSONResponse({'items': [e.__dict__ for e in items]})

    @app.get('/sse/stream_search_memory')
    async def http_stream_search_memory(request: Request, query: str, project: Optional[str] = None, k: int = 50, durationSec: int = 15):
        if not _auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)

        def gen():
            try:
                import time
                start = time.time()
                sent = 0
                last_ping = 0.0
                items = search_memory(con, query=query, project=project, tags=None, k=k)
                for e in items:
                    now = time.time()
                    if now - last_ping > 5.0:
                        yield "event: ping\n" + f"data: {{\"t\": {int(now)} }}\n\n"
                        last_ping = now
                    if now - start > durationSec:
                        break
                    yield f"event: message\n" + f"data: {json.dumps(e.__dict__, ensure_ascii=False)}\n\n"
                    sent += 1
                yield f"event: end\n" + f"data: {json.dumps({'count': sent})}\n\n"
            except Exception as e:
                yield f"event: error\n" + f"data: {json.dumps({'error': str(e)})}\n\n"
        return StreamingResponse(gen(), media_type='text/event-stream')

    @app.get('/mem')
    async def mem_ui():
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
          <title>Memory-MCP</title>
          <style>
            body { font-family: system-ui, sans-serif; background: #0b1220; color: #e0e6f0; padding: 20px; }
            section { background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
            label { display: block; margin: 6px 0; }
            input, textarea { width: 100%; background: #0b1220; color: #e0e6f0; border: 1px solid #374151; border-radius: 6px; padding: 8px; }
            button { background: #2563eb; color: white; border: 0; border-radius: 6px; padding: 8px 12px; cursor: pointer; margin-right: 6px; }
            pre { background: #0b1220; border: 1px solid #1f2937; border-radius: 8px; padding: 10px; max-height: 50vh; overflow: auto; }
          </style>
        </head>
        <body>
          <h1>Memory-MCP</h1>
          <section>
            <h2>Write Memory</h2>
            <label>Project <input id="proj" value="RoadNerd"/></label>
            <label>Scope <input id="scope" value="project"/></label>
            <label>Key <input id="mkey" placeholder="optional key"/></label>
            <label>Tags (comma) <input id="mtags" placeholder="decision,prompt"/></label>
            <label>Text <textarea id="mtext" rows="3">Example memory text</textarea></label>
            <button onclick="writeMem()">Write</button>
            <pre id="writeOut">(no op)</pre>
          </section>
          <section>
            <h2>Search</h2>
            <label>Query <input id="q" placeholder="tokens"/></label>
            <label>Project <input id="sproj" value="RoadNerd"/></label>
            <label>k <input id="sk" value="10"/></label>
            <button onclick="searchMem()">Search</button>
            <pre id="searchOut">(no results)</pre>
          </section>
          <script>
            function j(o){ return JSON.stringify(o, null, 2); }
            function headers(){
              const t = localStorage.getItem('MEM_TOKEN') || '';
              const h = {'Content-Type':'application/json'};
              if (t) h['Authorization'] = 'Bearer '+t;
              return h;
            }
            async function writeMem(){
              const body = {
                project: document.getElementById('proj').value,
                scope: document.getElementById('scope').value,
                key: document.getElementById('mkey').value || null,
                text: document.getElementById('mtext').value,
                tags: (document.getElementById('mtags').value||'').split(',').map(s=>s.trim()).filter(Boolean)
              };
              const r = await fetch('/actions/write_memory', {method:'POST', headers: headers(), body: JSON.stringify(body)});
              document.getElementById('writeOut').textContent = j(await r.json());
            }
            async function searchMem(){
              const body = {
                query: document.getElementById('q').value,
                project: document.getElementById('sproj').value,
                k: parseInt(document.getElementById('sk').value||'10')
              };
              const r = await fetch('/actions/search_memory', {method:'POST', headers: headers(), body: JSON.stringify(body)});
              document.getElementById('searchOut').textContent = j(await r.json());
            }
          </script>
        </body>
        </html>
        '''
        return html

    return app


def main():
    ap = argparse.ArgumentParser(description='Memory-MCP HTTP/SSE Server')
    ap.add_argument('--home', default=os.environ.get('MEM_HOME', os.path.expanduser('~/.roadnerd/memorydb')))
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=7090)
    args = ap.parse_args()

    home = Path(args.home)
    app = create_app(home)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
