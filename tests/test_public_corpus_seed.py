import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_public_corpus_seed_builds_retrieval_and_graph_databases(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    data_dir = tmp_path / "demo-data"
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = ""
    env["LABGRAPH_EXTRACTOR"] = "regex"

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "seed_public_corpus.py"),
            "--data-dir",
            str(data_dir),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Seeded 10 documents" in result.stdout
    retrieval_db = data_dir / "docrag.sqlite3"
    graph_db = data_dir / "labgraph.sqlite3"
    assert retrieval_db.is_file()
    assert graph_db.is_file()
    with sqlite3.connect(retrieval_db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 10
    with sqlite3.connect(graph_db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM labgraph_entities"
        ).fetchone()[0] > 0
