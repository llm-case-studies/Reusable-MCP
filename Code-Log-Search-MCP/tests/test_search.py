import os
import sys
from pathlib import Path

# Make 'server' package importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.search import perform_code_search, perform_logs_search


def test_perform_code_search(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.txt").write_text("hello world\nnum_predict = 128\nbye\n")
    (root / "b.py").write_text("# num_predict appears here too\n")

    hits = perform_code_search("num_predict", root, max_results=5, context_lines=0)
    assert len(hits) >= 1
    assert any("num_predict" in h.preview for h in hits)


def test_perform_logs_search(tmp_path: Path):
    logs = tmp_path / "logs"
    logs.mkdir()
    f = logs / "20250101.jsonl"
    f.write_text('{"mode":"brainstorm","msg":"ok"}\n{"mode":"judge","msg":"ok"}\n')

    res = perform_logs_search("brainstorm", logs, date="20250101", mode="brainstorm", max_results=10)
    assert len(res) == 1
    assert res[0]["mode"] == "brainstorm"
