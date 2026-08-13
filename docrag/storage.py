import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from .config import DB_PATH, ensure_dirs


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL,
  stored_path TEXT NOT NULL,
  content_sha256 TEXT NOT NULL UNIQUE,
  pages INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'upload',
  source_id TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id INTEGER NOT NULL,
  chunk_index INTEGER NOT NULL,
  page_start INTEGER,
  page_end INTEGER,
  text TEXT NOT NULL,
  embedding TEXT,
  token_count INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  text,
  filename UNINDEXED,
  page_start UNINDEXED,
  page_end UNINDEXED,
  content='',
  tokenize='porter unicode61'
);
"""


FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  text,
  filename UNINDEXED,
  page_start UNINDEXED,
  page_end UNINDEXED,
  content='',
  tokenize='porter unicode61'
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(documents)")
        }
        if "source_type" not in columns:
            conn.execute(
                "ALTER TABLE documents ADD COLUMN source_type TEXT NOT NULL DEFAULT 'upload'"
            )
        if "source_id" not in columns:
            conn.execute("ALTER TABLE documents ADD COLUMN source_id TEXT")


def document_by_hash(content_sha256: str) -> Optional[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM documents WHERE content_sha256 = ?",
            (content_sha256,),
        ).fetchone()


def get_document(document_id: int) -> Optional[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()


def create_document(
    filename: str,
    stored_path: Path,
    content_sha256: str,
    pages: int,
    *,
    source_type: str = "upload",
    source_id: Optional[str] = None,
) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO documents
              (filename, stored_path, content_sha256, pages, created_at, source_type, source_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                filename,
                str(stored_path),
                content_sha256,
                pages,
                datetime.now(timezone.utc).isoformat(),
                source_type,
                source_id,
            ),
        )
        return int(cursor.lastrowid)


def add_chunks(document_id: int, filename: str, chunks: Iterable[Dict]) -> None:
    with connect() as conn:
        for chunk in chunks:
            cursor = conn.execute(
                """
                INSERT INTO chunks
                  (document_id, chunk_index, page_start, page_end, text, embedding, token_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    chunk["chunk_index"],
                    chunk.get("page_start"),
                    chunk.get("page_end"),
                    chunk["text"],
                    json.dumps(chunk["embedding"]) if chunk.get("embedding") else None,
                    len(chunk["text"].split()),
                ),
            )
            conn.execute(
                """
                INSERT INTO chunks_fts(rowid, text, filename, page_start, page_end)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    cursor.lastrowid,
                    chunk["text"],
                    filename,
                    chunk.get("page_start"),
                    chunk.get("page_end"),
                ),
            )


def list_documents() -> List[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT d.*, COUNT(c.id) AS chunks, GROUP_CONCAT(c.id) AS chunk_ids
            FROM documents d
            LEFT JOIN chunks c ON c.document_id = d.id
            GROUP BY d.id
            ORDER BY d.created_at DESC
            """
        ).fetchall()


def rename_document(document_id: int, filename: str) -> Optional[sqlite3.Row]:
    with connect() as conn:
        result = conn.execute(
            "UPDATE documents SET filename = ? WHERE id = ?",
            (filename, document_id),
        )
        if result.rowcount == 0:
            return None
        return conn.execute(
            "SELECT * FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()


def rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS chunks_fts")
    conn.executescript(FTS_SCHEMA)
    conn.execute(
        """
        INSERT INTO chunks_fts(rowid, text, filename, page_start, page_end)
        SELECT c.id, c.text, d.filename, c.page_start, c.page_end
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        """
    )


def delete_document(document_id: int) -> Optional[sqlite3.Row]:
    with connect() as conn:
        document = conn.execute(
            "SELECT * FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
        if not document:
            return None
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        rebuild_fts(conn)
        return document


def get_chunk(chunk_id: int) -> Optional[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT c.*, d.filename
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.id = ?
            """,
            (chunk_id,),
        ).fetchone()


def chunks_for_document(document_id: int) -> List[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT c.id, c.text, d.filename
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.document_id = ?
            ORDER BY c.chunk_index
            """,
            (document_id,),
        ).fetchall()


def all_embedded_chunks() -> List[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT c.*, d.filename
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.embedding IS NOT NULL
            """
        ).fetchall()


def search_fts(query: str, limit: int) -> List[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT
              c.id,
              c.text,
              c.page_start,
              c.page_end,
              d.filename,
              bm25(chunks_fts) AS score
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.rowid
            JOIN documents d ON d.id = c.document_id
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
