#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
    from pydantic import BaseModel
    import uvicorn
except Exception:
    print("Missing dependencies: fastapi, uvicorn")
    print("Create a venv and: pip install fastapi uvicorn")
    raise SystemExit(1)

from .storage import init_db, write_memory, read_memory, search_memory, list_memories


# ----- Pydantic models for better OpenAPI docs -----
class MemoryEntryModel(BaseModel):
    id: str
    version: int
    project: Optional[str] = None
    key: Optional[str] = None
    scope: str
    text: str
    tags: List[str] = []
    createdAt: str
    ttlSec: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class WriteMemoryRequest(BaseModel):
    project: Optional[str] = None
    scope: str = 'project'
    key: Optional[str] = None
    text: str
    tags: Optional[List[str]] = None
    ttlSec: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ReadMemoryRequest(BaseModel):
    id: Optional[str] = None
    project: Optional[str] = None
    key: Optional[str] = None


class ReadMemoryResponse(BaseModel):
    entry: Optional[MemoryEntryModel] = None


class SearchMemoryRequest(BaseModel):
    query: str
    project: Optional[str] = None
    tags: Optional[List[str]] = None
    k: int = 20


class SearchMemoryResponse(BaseModel):
    items: List[MemoryEntryModel]


class ListMemoriesRequest(BaseModel):
    project: Optional[str] = None
    tags: Optional[List[str]] = None
    limit: int = 50
    offset: int = 0


class ListMemoriesResponse(BaseModel):
    items: List[MemoryEntryModel]


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
    PROTOCOL_VERSION = '2025-06-18'

    def _memory_entry_schema():
        return {
            'type': ['object', 'null'],
            'description': 'Versioned memory entry (null when not found).',
            'properties': {
                'id': {'type': 'string', 'description': 'Unique memory id (UUID).'},
                'version': {'type': 'integer', 'description': 'Monotonic version per project+key.'},
                'project': {'type': ['string','null'], 'description': 'Project namespace.'},
                'key': {'type': ['string','null'], 'description': 'Optional memory key (name).'},
                'scope': {'type': 'string', 'enum': ['project','global'], 'description': 'Scope selection.'},
                'text': {'type': 'string', 'description': 'Entry body.'},
                'tags': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Free‑form labels.'},
                'createdAt': {'type': 'string', 'format': 'date-time', 'description': 'Creation timestamp (ISO8601).'},
                'ttlSec': {'type': ['integer','null'], 'description': 'Optional time‑to‑live in seconds.'},
                'metadata': {'type': ['object','null'], 'description': 'Arbitrary JSON metadata.'}
            },
            'required': ['id','version','scope','text','tags','createdAt']
        }

    def mcp_tools():
        entry_schema = _memory_entry_schema()
        return [
            {
                'name': 'write_memory',
                'title': 'Write Memory',
                'description': 'Append a memory; if project+key provided, bump version and store latest.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project': {'type': ['string','null'], 'description': 'Project name (optional).'},
                        'scope': {'type': 'string', 'enum': ['project', 'global'], 'default': 'project', 'description': 'Scope: project or global.'},
                        'key': {'type': ['string','null'], 'description': 'Optional key (name) for versioned reads.'},
                        'text': {'type': 'string', 'description': 'Entry body text.'},
                        'tags': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Labels, e.g., ["decision","prompt"].'},
                        'ttlSec': {'type': ['integer','null'], 'minimum': 1, 'description': 'Optional TTL seconds.'},
                        'metadata': {'type': ['object','null'], 'description': 'Arbitrary JSON metadata.'}
                    },
                    'required': ['text']
                },
                'outputSchema': {
                    'type': 'object',
                    'properties': {
                        'entry': entry_schema
                    },
                    'required': ['entry']
                }
            },
            {
                'name': 'read_memory',
                'title': 'Read Memory',
                'description': 'Read by id or latest by project+key; returns null when not found.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': ['string','null'], 'description': 'Exact entry id (UUID).'},
                        'project': {'type': ['string','null'], 'description': 'Project to resolve latest by key.'},
                        'key': {'type': ['string','null'], 'description': 'Key (name) to resolve latest entry.'}
                    },
                    'description': 'Provide either id, or project+key.'
                },
                'outputSchema': {
                    'type': 'object',
                    'properties': {
                        'entry': entry_schema
                    },
                    'required': ['entry']
                }
            },
            {
                'name': 'search_memory',
                'title': 'Search Memory',
                'description': 'Full‑text search (FTS) over saved entries.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string', 'description': 'Search string (FTS query).'},
                        'project': {'type': ['string','null'], 'description': 'Limit search to a project.'},
                        'tags': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Filter: entry must include these tags.'},
                        'k': {'type': 'integer', 'default': 20, 'minimum': 1, 'maximum': 200, 'description': 'Max items to return.'}
                    },
                    'required': ['query']
                },
                'outputSchema': {
                    'type': 'object',
                    'properties': {
                        'items': {'type': 'array', 'items': _memory_entry_schema(), 'description': 'Matching entries.'}
                    },
                    'required': ['items']
                }
            },
            {
                'name': 'list_memories',
                'title': 'List Memories',
                'description': 'List recent entries with optional filters.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project': {'type': ['string','null'], 'description': 'Limit to a project.'},
                        'tags': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Filter by tags (contains all).'},
                        'limit': {'type': 'integer', 'default': 50, 'minimum': 1, 'maximum': 500, 'description': 'Page size.'},
                        'offset': {'type': 'integer', 'default': 0, 'minimum': 0, 'description': 'Page offset.'}
                    }
                },
                'outputSchema': {
                    'type': 'object',
                    'properties': {
                        'items': {'type': 'array', 'items': _memory_entry_schema(), 'description': 'Recent entries.'}
                    },
                    'required': ['items']
                }
            },
        ]

    @app.get('/healthz')
    def healthz():
        return {'ok': True, 'home': str(home)}

    @app.post('/actions/write_memory', response_model=MemoryEntryModel)
    async def http_write_memory(request: Request, body: WriteMemoryRequest):
        if not _auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        entry = write_memory(
            con,
            home,
            project=body.project,
            scope=body.scope or 'project',
            key=body.key,
            text=body.text or '',
            tags=body.tags or [],
            ttl_sec=body.ttlSec,
            metadata=body.metadata,
        )
        return JSONResponse(entry.__dict__)

    @app.post('/actions/read_memory', response_model=ReadMemoryResponse)
    async def http_read_memory(request: Request, body: ReadMemoryRequest):
        if not _auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        entry = read_memory(con, id=body.id, project=body.project, key=body.key)
        return JSONResponse({'entry': entry.__dict__ if entry else None})

    @app.post('/actions/search_memory', response_model=SearchMemoryResponse)
    async def http_search_memory(request: Request, body: SearchMemoryRequest):
        if not _auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        items = search_memory(con, query=body.query or '', project=body.project, tags=body.tags or [], k=int(body.k or 20))
        return JSONResponse({'items': [e.__dict__ for e in items]})

    @app.post('/actions/list_memories', response_model=ListMemoriesResponse)
    async def http_list_memories(request: Request, body: ListMemoriesRequest):
        if not _auth_ok(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        items = list_memories(con, project=body.project, tags=body.tags or [], limit=int(body.limit), offset=int(body.offset))
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

    # ---- Minimal MCP Streamable HTTP endpoint ----
    @app.get('/mcp')
    async def mcp_get():
        # We don't expose a long-lived SSE stream for GET in this minimal implementation.
        return JSONResponse({'error': 'method not allowed'}, status_code=405)

    def _mcp_response(id_value, result=None, error=None):
        if error is not None:
            return {'jsonrpc': '2.0', 'id': id_value, 'error': error}
        return {'jsonrpc': '2.0', 'id': id_value, 'result': result}

    def _text_and_structured(obj: Any):
        return {
            'content': [{'type': 'text', 'text': json.dumps(obj, ensure_ascii=False)}],
            'structuredContent': obj,
            'isError': False,
        }

    @app.post('/mcp')
    async def mcp_post(request: Request):
        # Accept either a single JSON-RPC message or a batch (list)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({'error': 'invalid json'}, status_code=400)

        async def handle_one(msg):
            method = msg.get('method')
            msg_id = msg.get('id')
            params = msg.get('params') or {}

            # Notifications have no id
            is_notification = ('id' not in msg)

            if method == 'initialize':
                # Negotiate version; accept requested or reply with supported
                requested = (params or {}).get('protocolVersion')
                result = {
                    'protocolVersion': requested or PROTOCOL_VERSION,
                    'capabilities': {
                        'tools': {'listChanged': False},
                    },
                    'serverInfo': {
                        'name': 'Memory-MCP',
                        'title': 'Memory MCP',
                        'version': '0.1.0',
                    },
                    'instructions': 'Provide durable, project-scoped memory via tools.',
                }
                return _mcp_response(msg_id, result=result)

            if method == 'notifications/initialized':
                # Acknowledge; no response per JSON-RPC for notifications
                return None

            if method == 'tools/list':
                # Omit nextCursor when there is no pagination token to avoid clients
                # rejecting `null` (some validate as string if present).
                return _mcp_response(msg_id, result={'tools': mcp_tools()})

            if method == 'tools/call':
                name = (params or {}).get('name')
                arguments = (params or {}).get('arguments') or {}
                try:
                    if name == 'write_memory':
                        entry = write_memory(
                            con,
                            home,
                            project=arguments.get('project'),
                            scope=(arguments.get('scope') or 'project'),
                            key=arguments.get('key'),
                            text=arguments.get('text') or '',
                            tags=arguments.get('tags') or [],
                            ttl_sec=arguments.get('ttlSec'),
                            metadata=arguments.get('metadata'),
                        )
                        return _mcp_response(msg_id, result=_text_and_structured(entry.__dict__))
                    elif name == 'read_memory':
                        entry = read_memory(
                            con,
                            id=arguments.get('id'),
                            project=arguments.get('project'),
                            key=arguments.get('key'),
                        )
                        return _mcp_response(msg_id, result=_text_and_structured({'entry': entry.__dict__ if entry else None}))
                    elif name == 'search_memory':
                        items = search_memory(
                            con,
                            query=arguments.get('query') or '',
                            project=arguments.get('project'),
                            tags=arguments.get('tags') or [],
                            k=int(arguments.get('k') or 20),
                        )
                        return _mcp_response(msg_id, result=_text_and_structured({'items': [e.__dict__ for e in items]}))
                    elif name == 'list_memories':
                        items = list_memories(
                            con,
                            project=arguments.get('project'),
                            tags=arguments.get('tags') or [],
                            limit=int(arguments.get('limit') or 50),
                            offset=int(arguments.get('offset') or 0),
                        )
                        return _mcp_response(msg_id, result=_text_and_structured({'items': [e.__dict__ for e in items]}))
                    else:
                        return _mcp_response(msg_id, error={'code': -32602, 'message': f'Unknown tool: {name}'})
                except Exception as e:
                    return _mcp_response(msg_id, result={'content': [{'type': 'text', 'text': f'Error: {e}'}], 'isError': True})

            if method == 'ping':
                return _mcp_response(msg_id, result={'ok': True})

            # Unknown method
            return _mcp_response(msg_id, error={'code': -32601, 'message': f'Unknown method: {method}'})

        # Process single or batch
        if isinstance(body, list):
            out = []
            for m in body:
                resp = await handle_one(m)
                if resp is not None:
                    out.append(resp)
            # If all were notifications, return 202 with no body
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
        return HTMLResponse(content=html)

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
