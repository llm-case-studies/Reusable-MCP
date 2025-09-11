#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import List

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
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

    @app.get('/healthz')
    def healthz():
        return {'ok': True}

    @app.post('/actions/search_previous_chats')
    async def search_previous_chats(req: Request):
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
        body = await req.json()
        chat_id = body.get('chat_id')
        # Minimal placeholder (decisions table out of scope for v1)
        return JSONResponse({'decisions': [], 'note': 'decision extraction TBD'})

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

