#!/usr/bin/env python3
"""Build an offline LabGraph demo database from the checked-in public corpus."""

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "examples" / "public_corpus"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        required=True,
        type=Path,
        help="New or empty directory where demo SQLite databases will be created.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    data_dir = args.data_dir.resolve()
    database_paths = (data_dir / "docrag.sqlite3", data_dir / "labgraph.sqlite3")
    if any(path.exists() for path in database_paths):
        sys.stderr.write(
            "Refusing to overwrite an existing demo database. Choose a new --data-dir.\n"
        )
        return 2

    os.environ["LABGRAPH_DATA_DIR"] = str(data_dir)
    os.environ["LABGRAPH_DB_PATH"] = str(data_dir / "labgraph.sqlite3")
    os.environ["LABGRAPH_EXTRACTOR"] = "regex"
    os.environ["OPENAI_API_KEY"] = ""
    sys.path.insert(0, str(ROOT))

    from docrag.config import ensure_dirs
    from docrag.ingest import ingest_file
    from docrag.storage import init_db

    ensure_dirs()
    init_db()
    documents = sorted(CORPUS_DIR.glob("*.md"))
    for document in documents:
        result = ingest_file(document, document.name)
        if result["status"] != "ingested":
            raise RuntimeError(f"Could not seed {document.name}: {result['status']}")

    sys.stdout.write(f"Seeded {len(documents)} documents into {data_dir}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
