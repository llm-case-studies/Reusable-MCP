#!/usr/bin/env python3
import argparse
import json
import sqlite3
from pathlib import Path


def init_db(db: Path):
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages(
          id INTEGER PRIMARY KEY,
          chat_id TEXT,
          project TEXT,
          ts TEXT,
          role TEXT,
          text TEXT,
          tags TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_messages USING fts5(text, content='messages', content_rowid='id');
        CREATE TABLE IF NOT EXISTS decisions(
          id INTEGER PRIMARY KEY,
          chat_id TEXT,
          ts TEXT,
          key TEXT,
          value TEXT,
          file_path TEXT
        );
        """
    )
    con.commit()
    return con


def index_transcripts(home: Path):
    db = home / 'index.sqlite'
    con = init_db(db)
    cur = con.cursor()

    tdir = home / 'transcripts'
    tdir.mkdir(parents=True, exist_ok=True)

    for jf in sorted(tdir.glob('*.jsonl')):
        with jf.open(encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                tags = ' '.join(obj.get('tags', [])) if obj.get('tags') else ''
                cur.execute(
                    "INSERT INTO messages(chat_id, project, ts, role, text, tags) VALUES (?,?,?,?,?,?)",
                    (obj.get('chat_id'), obj.get('project'), obj.get('ts'), obj.get('role'), obj.get('text'), tags),
                )
                rowid = cur.lastrowid
                cur.execute("INSERT INTO fts_messages(rowid, text) VALUES (?,?)", (rowid, obj.get('text') or ''))

    con.commit()
    con.close()
    print(f"Indexed transcripts into {db}")


def main():
    ap = argparse.ArgumentParser(description="Build SQLite FTS index from JSONL transcripts")
    ap.add_argument('--home', required=True)
    args = ap.parse_args()

    home = Path(args.home)
    home.mkdir(parents=True, exist_ok=True)
    index_transcripts(home)


if __name__ == '__main__':
    main()

