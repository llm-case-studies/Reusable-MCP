#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description="Append a transcript row to JSONL store")
    ap.add_argument('--home', default=os.environ.get('PRIOR_SELF_HOME', os.path.expanduser('~/.roadnerd/chatdb')))
    ap.add_argument('--chat-id', required=True)
    ap.add_argument('--project', required=True)
    ap.add_argument('--role', required=True, choices=['user', 'assistant', 'tool'])
    ap.add_argument('--text', required=True)
    ap.add_argument('--tags', nargs='*')
    ap.add_argument('--tool-name')
    args = ap.parse_args()

    home = Path(args.home)
    outdir = home / 'transcripts'
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{args.project}.jsonl"

    row = {
        'chat_id': args.chat_id,
        'project': args.project,
        'ts': datetime.now().isoformat(),
        'role': args.role,
        'text': args.text,
    }
    if args.tags:
        row['tags'] = args.tags
    if args.tool_name:
        row['tool_name'] = args.tool_name

    with out.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')

    print(f"Appended to {out}")


if __name__ == '__main__':
    main()

