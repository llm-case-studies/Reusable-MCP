#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import List, Optional

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, StreamingResponse
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

    @app.get('/healthz')
    def healthz():
        return {'ok': True, 'code_root': str(default_code_root), 'logs_root': str(logs_root)}

    @app.post('/actions/search_code')
    async def search_code(req: Request):
        if not _auth_ok(req):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        body = await req.json()
        query = body.get('query') or ''
        root = Path(body.get('root') or default_code_root)
        globs = body.get('globs') or []
        max_results = int(body.get('maxResults', 100))
        context_lines = int(body.get('contextLines', 0))
        hits = perform_code_search(query, root, globs, max_results, context_lines)
        return JSONResponse({'hits': [h.__dict__ for h in hits]})

    @app.get('/sse/search_code_stream')
    async def search_code_stream(request: Request, query: str, root: Optional[str] = None, maxResults: int = 200, durationSec: int = 20):
        if not _auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        root_path = Path(root or default_code_root)

        def event_stream():
            try:
                import time
                start = time.time()
                sent = 0
                last_ping = 0.0
                hits = perform_code_search(query, root_path, None, maxResults, 0)
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
        results = perform_logs_search(query, logs_root, date=date, mode=mode, max_results=max_results)
        return JSONResponse({'entries': results})

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
    args = ap.parse_args()

    default_code_root = Path(args.default_code_root)
    logs_root = Path(args.logs_root)
    logs_root.mkdir(parents=True, exist_ok=True)
    app = create_app(default_code_root, logs_root)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
