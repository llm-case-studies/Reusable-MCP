#!/usr/bin/env python3
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any


@dataclass
class MemoryEntry:
    id: str
    version: int
    project: Optional[str]
    key: Optional[str]
    scope: str
    text: str
    tags: List[str]
    createdAt: str
    ttlSec: Optional[int]
    metadata: Optional[Dict[str, Any]]


def init_db(home: Path) -> sqlite3.Connection:
    home.mkdir(parents=True, exist_ok=True)
    db = home / 'memory.sqlite'
    con = sqlite3.connect(str(db), check_same_thread=False)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS memories(
          rowid INTEGER PRIMARY KEY AUTOINCREMENT,
          id TEXT UNIQUE,
          version INTEGER,
          project TEXT,
          key TEXT,
          scope TEXT,
          text TEXT,
          tags TEXT,
          created_at TEXT,
          ttl_sec INTEGER,
          metadata TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_memories USING fts5(
          text, tags, project, key, scope, content='memories', content_rowid='rowid'
        );
        """
    )
    con.commit()
    return con


def _to_entry(row: sqlite3.Row) -> MemoryEntry:
    tags = (row['tags'] or '').split(',') if row['tags'] else []
    md = None
    if row['metadata']:
        try:
            md = json.loads(row['metadata'])
        except Exception:
            md = None
    return MemoryEntry(
        id=row['id'],
        version=row['version'],
        project=row['project'],
        key=row['key'],
        scope=row['scope'],
        text=row['text'],
        tags=tags,
        createdAt=row['created_at'],
        ttlSec=row['ttl_sec'],
        metadata=md,
    )


def write_memory(con: sqlite3.Connection, home: Path, *, project: Optional[str], scope: str, key: Optional[str], text: str, tags: Optional[List[str]] = None, ttl_sec: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> MemoryEntry:
    cur = con.cursor()
    # versioning: if project+key present, increment; else start at 1
    version = 1
    if key:
        cur.execute("SELECT MAX(version) FROM memories WHERE project IS ? AND key IS ?", (project, key))
        row = cur.fetchone()
        if row and row[0]:
            version = int(row[0]) + 1

    mid = str(uuid.uuid4())
    # RFC3339 compliant timestamp with timezone
    now = datetime.now(timezone.utc).isoformat()
    tags_str = ','.join(tags) if tags else ''
    md_json = json.dumps(metadata) if metadata else None

    cur.execute(
        "INSERT INTO memories(id, version, project, key, scope, text, tags, created_at, ttl_sec, metadata) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (mid, version, project, key, scope, text, tags_str, now, ttl_sec, md_json),
    )
    # sync FTS row
    cur.execute(
        "INSERT INTO fts_memories(rowid, text, tags, project, key, scope) VALUES (last_insert_rowid(), ?, ?, ?, ?, ?)",
        (text, tags_str, project, key, scope),
    )
    con.commit()

    # Audit log
    audit = home / 'audit.jsonl'
    with audit.open('a', encoding='utf-8') as f:
        f.write(json.dumps({
            'ts': now,
            'action': 'write',
            'id': mid,
            'version': version,
            'project': project,
            'key': key,
            'scope': scope,
            'tags': tags,
        }, ensure_ascii=False) + '\n')

    cur = con.cursor()
    cur = con.execute("SELECT * FROM memories WHERE id = ?", (mid,))
    return _to_entry(cur.fetchone())


def read_memory(con: sqlite3.Connection, *, id: Optional[str] = None, project: Optional[str] = None, key: Optional[str] = None) -> Optional[MemoryEntry]:
    if id:
        cur = con.execute("SELECT * FROM memories WHERE id = ?", (id,))
        row = cur.fetchone()
        return _to_entry(row) if row else None
    if project is not None and key is not None:
        cur = con.execute(
            "SELECT * FROM memories WHERE project IS ? AND key IS ? ORDER BY version DESC LIMIT 1",
            (project, key),
        )
        row = cur.fetchone()
        return _to_entry(row) if row else None
    return None


def search_memory(con: sqlite3.Connection, *, query: str, project: Optional[str] = None, tags: Optional[List[str]] = None, k: int = 20) -> List[MemoryEntry]:
    # Use FTS MATCH; if project/tags filters present, intersect
    # To avoid parse errors like "no such column: ..." when users pass special tokens,
    # treat the input as a single phrase by quoting it for FTS5.
    q = (query or '').replace('"', ' ')
    q = f'"{q.strip()}"' if q.strip() else '""'
    sql = "SELECT m.* FROM fts_memories f JOIN memories m ON f.rowid = m.rowid WHERE f.text MATCH ?"
    args: List[Any] = [q]
    if project is not None:
        sql += " AND m.project IS ?"
        args.append(project)
    if tags:
        for t in tags:
            sql += " AND m.tags LIKE ?"
            args.append(f"%{t}%")
    sql += " LIMIT ?"
    args.append(k)
    cur = con.execute(sql, args)
    return [_to_entry(row) for row in cur.fetchall()]


def list_memories(con: sqlite3.Connection, *, project: Optional[str] = None, tags: Optional[List[str]] = None, limit: int = 50, offset: int = 0) -> List[MemoryEntry]:
    sql = "SELECT * FROM memories"
    clauses = []
    args: List[Any] = []
    if project is not None:
        clauses.append("project IS ?")
        args.append(project)
    if tags:
        for t in tags:
            clauses.append("tags LIKE ?")
            args.append(f"%{t}%")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    cur = con.execute(sql, args)
    return [_to_entry(row) for row in cur.fetchall()]
