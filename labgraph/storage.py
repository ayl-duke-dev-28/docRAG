import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .graph import LabGraph
from .schema import Entity, EntityKind, Relation, RelationKind


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS labgraph_entities (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    attrs TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS ix_labgraph_entities_kind
    ON labgraph_entities(kind);

CREATE TABLE IF NOT EXISTS labgraph_relations (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    provenance TEXT NOT NULL DEFAULT '[]',
    attrs TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (source_id, target_id, kind, provenance),
    FOREIGN KEY (source_id) REFERENCES labgraph_entities(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES labgraph_entities(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_labgraph_relations_source
    ON labgraph_relations(source_id);
CREATE INDEX IF NOT EXISTS ix_labgraph_relations_target
    ON labgraph_relations(target_id);
CREATE INDEX IF NOT EXISTS ix_labgraph_relations_kind
    ON labgraph_relations(kind);
"""


@contextmanager
def _connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


def save_graph(graph: LabGraph, db_path: Path) -> None:
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM labgraph_relations")
        conn.execute("DELETE FROM labgraph_entities")
        for entity in graph.entities():
            conn.execute(
                """
                INSERT INTO labgraph_entities (id, kind, name, aliases, attrs)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entity.id,
                    entity.kind.value,
                    entity.name,
                    json.dumps(list(entity.aliases)),
                    json.dumps([list(pair) for pair in entity.attrs]),
                ),
            )
        for relation in graph.relations():
            conn.execute(
                """
                INSERT OR REPLACE INTO labgraph_relations
                    (source_id, target_id, kind, provenance, attrs)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    relation.source_id,
                    relation.target_id,
                    relation.kind.value,
                    json.dumps(list(relation.provenance)),
                    json.dumps([list(pair) for pair in relation.attrs]),
                ),
            )


def load_graph(db_path: Path) -> LabGraph:
    graph = LabGraph()
    if not db_path.exists():
        return graph
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, kind, name, aliases, attrs FROM labgraph_entities"
        ).fetchall()
        for row in rows:
            graph.add_entity(
                Entity(
                    id=row["id"],
                    kind=EntityKind(row["kind"]),
                    name=row["name"],
                    aliases=tuple(json.loads(row["aliases"])),
                    attrs=tuple(
                        (pair[0], pair[1]) for pair in json.loads(row["attrs"])
                    ),
                )
            )

        edge_rows = conn.execute(
            "SELECT source_id, target_id, kind, provenance, attrs FROM labgraph_relations"
        ).fetchall()
        for row in edge_rows:
            graph.add_relation(
                Relation(
                    source_id=row["source_id"],
                    target_id=row["target_id"],
                    kind=RelationKind(row["kind"]),
                    provenance=tuple(json.loads(row["provenance"])),
                    attrs=tuple(
                        (pair[0], pair[1]) for pair in json.loads(row["attrs"])
                    ),
                )
            )
    return graph
