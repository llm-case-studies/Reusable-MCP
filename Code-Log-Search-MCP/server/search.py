#!/usr/bin/env python3
import json
import os
import re
import subprocess
import time
import select
import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


@dataclass
class CodeHit:
    file: str
    line: int
    preview: str


def _rg_available() -> bool:
    exists = Path('/usr/bin/rg').exists()
    print(f"rg exists: {exists}")
    return exists


def perform_code_search(
    query: str,
    root: Path,
    globs: Optional[List[str]] = None,
    max_results: int = 100,
    context_lines: int = 0,
    literal: bool = False,
    timeout_ms: Optional[int] = None,
) -> List[CodeHit]:
    if not _rg_available():
        raise RuntimeError('ripgrep (rg) not found on PATH')
    if not root.exists():
        raise FileNotFoundError(f'root not found: {root}')

    cmd = ['/usr/bin/rg', '--json', '--no-heading', '--line-number', '--color', 'never']
    if literal:
        cmd.append('-F')
    if context_lines > 0:
        cmd += ['-C', str(context_lines)]
    if globs:
        for g in globs:
            cmd += ['-g', g]
    # End of options: ensure user-supplied query is treated as positional
    cmd.append('--')
    cmd += [query, str(root)]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    hits: List[CodeHit] = []
    deadline = None
    if timeout_ms and int(timeout_ms) > 0:
        deadline = time.time() + (int(timeout_ms) / 1000.0)
    try:
        assert proc.stdout is not None
        fd = proc.stdout
        while True:
            # Timeout check
            if deadline and time.time() > deadline:
                try:
                    proc.kill()
                finally:
                    break
            # Read with a short poll to avoid blocking
            rlist, _, _ = select.select([fd], [], [], 0.1)
            if not rlist:
                # Process exited?
                if proc.poll() is not None:
                    break
                continue
            line = fd.readline()
            if not line:
                if proc.poll() is not None:
                    break
                continue
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get('type') == 'match':
                data = obj.get('data', {})
                path = data.get('path', {}).get('text')
                line_number = data.get('line_number')
                lines = data.get('lines', {}).get('text', '').rstrip('\n')
                if path and line_number is not None:
                    hits.append(CodeHit(file=path, line=int(line_number), preview=lines))
                    if len(hits) >= max_results:
                        break
        return hits
    finally:
        with contextlib.suppress(Exception):
            proc.kill()
        with contextlib.suppress(Exception):
            if proc.stdout:
                proc.stdout.close()
        with contextlib.suppress(Exception):
            if proc.stderr:
                proc.stderr.close()
    return hits


def perform_logs_search(query: str, logs_root: Path, date: Optional[str] = None,
                        mode: Optional[str] = None, max_results: int = 200) -> List[dict]:
    target: Optional[Path] = None
    if date:
        cand = logs_root / f'{date}.jsonl'
        if cand.exists():
            target = cand
    if target is None:
        files = sorted(logs_root.glob('*.jsonl'))
        if files:
            target = files[-1]
    if target is None:
        return []

    # Prepare regex for query (case-insensitive substring by default)
    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error:
        # Fallback: escape special chars
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    results: List[dict] = []
    with target.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if mode and obj.get('mode') != mode:
                continue
            # Match against whole JSON string for simplicity; could be improved to fields
            if pattern.search(line):
                results.append(obj)
                if len(results) >= max_results:
                    break
    return results
