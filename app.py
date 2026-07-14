import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from docrag.config import BASE_DIR, LABGRAPH_DB_PATH, UPLOAD_DIR
from docrag.ingest import ingest_file
from docrag.retrieval import answer, source
from docrag.storage import delete_document, get_document, init_db, list_documents, rename_document
from labgraph.graph import LabGraph
from labgraph.schema import Entity, EntityKind
from labgraph.storage import load_graph


app = FastAPI(title="LabGraph", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class QueryRequest(BaseModel):
    question: str
    top_k: int = 6


class RenameDocumentRequest(BaseModel):
    filename: str


class QueryTraceRequest(BaseModel):
    source_id: Optional[str] = None
    target_id: Optional[str] = None
    max_depth: int = 4


def clean_document_filename(filename: str) -> str:
    cleaned = filename.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Filename is required.")
    if "/" in cleaned or "\\" in cleaned:
        raise HTTPException(status_code=400, detail="Filename cannot contain path separators.")
    if cleaned in {".", ".."}:
        raise HTTPException(status_code=400, detail="Filename is invalid.")
    return cleaned


def stored_upload_path(stored_path: str) -> Path:
    path = Path(stored_path).resolve()
    upload_root = UPLOAD_DIR.resolve()
    if path.parent != upload_root:
        raise HTTPException(status_code=400, detail="Stored file path is invalid.")
    return path


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/documents")
def documents():
    return [dict(row) for row in list_documents()]


def entity_to_dict(entity: Entity) -> Dict:
    return {
        "id": entity.id,
        "kind": entity.kind.value,
        "name": entity.name,
        "aliases": list(entity.aliases),
        "attrs": entity.as_attrs_dict(),
    }


def compact_entity(entity: Entity) -> Dict:
    return {
        "id": entity.id,
        "kind": entity.kind.value,
        "name": entity.name,
    }


def compact_relation(relation) -> Dict:
    return {
        "source_id": relation.source_id,
        "target_id": relation.target_id,
        "kind": relation.kind.value,
        "provenance": list(relation.provenance),
        "attrs": relation.as_attrs_dict(),
    }


def graph_trace_response(graph: LabGraph, path: List[str]) -> Dict:
    entities = [graph.get_entity(entity_id) for entity_id in path]
    if not path or any(entity is None for entity in entities):
        return {"found": False, "trace": [], "path": [], "relations": []}

    compact_path = [compact_entity(entity) for entity in entities if entity is not None]
    relations = []
    for source_id, target_id in zip(path, path[1:]):
        between = graph.relations_between(source_id, target_id)
        if between:
            relations.append(compact_relation(between[0]))
    return {
        "found": True,
        "trace": [entity["name"] for entity in compact_path],
        "path": compact_path,
        "relations": relations,
    }


def default_trace(graph: LabGraph, max_depth: int) -> List[str]:
    people = list(graph.entities(kind=EntityKind.PERSON))
    decisions = list(graph.entities(kind=EntityKind.DECISION))
    for person in people:
        for decision in decisions:
            path = graph.shortest_path(person.id, decision.id, max_depth=max_depth)
            if path:
                return path
    return []


@app.get("/api/labgraph/stats")
def labgraph_stats():
    graph = load_graph(LABGRAPH_DB_PATH)
    counts = {
        kind.value: len(list(graph.entities(kind=kind)))
        for kind in EntityKind
    }
    return {
        "status": "ok",
        "entities": graph.entity_count,
        "relations": graph.relation_count,
        "entity_kinds": counts,
    }


@app.get("/api/labgraph/entities")
def labgraph_entities(kind: Optional[str] = None):
    graph = load_graph(LABGRAPH_DB_PATH)
    entity_kind = None
    if kind is not None:
        try:
            entity_kind = EntityKind(kind)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Unknown entity kind.") from exc
    return [entity_to_dict(entity) for entity in graph.entities(kind=entity_kind)]


@app.post("/api/labgraph/query-trace")
def labgraph_query_trace(request: QueryTraceRequest):
    graph = load_graph(LABGRAPH_DB_PATH)
    max_depth = max(1, min(request.max_depth, 8))
    if request.source_id and request.target_id:
        path = graph.shortest_path(request.source_id, request.target_id, max_depth=max_depth)
    else:
        path = default_trace(graph, max_depth=max_depth)
    return graph_trace_response(graph, path)


@app.patch("/api/documents/{document_id}")
def rename_document_api(document_id: int, request: RenameDocumentRequest):
    filename = clean_document_filename(request.filename)
    document = rename_document(document_id, filename)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    return dict(document)


@app.delete("/api/documents/{document_id}")
def delete_document_api(document_id: int):
    existing = get_document(document_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found.")
    path = stored_upload_path(existing["stored_path"])

    document = delete_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    if path.exists():
        path.unlink()
    return {"status": "deleted", "document_id": document_id}


@app.get("/api/documents/{document_id}/file")
def document_file(document_id: int):
    document = get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    path = stored_upload_path(document["stored_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Stored file not found.")
    return FileResponse(path, filename=document["filename"])


@app.get("/api/health")
def health():
    docs = list_documents()
    return {
        "status": "ok",
        "documents": len(docs),
        "chunks": sum(row["chunks"] for row in docs),
    }


@app.post("/api/upload")
async def upload(files: List[UploadFile] = File(...)):
    results = []
    for uploaded in files:
        suffix = Path(uploaded.filename or "").suffix.lower()
        if suffix not in {".pdf", ".txt", ".md"}:
            raise HTTPException(status_code=400, detail="Only PDF, TXT, and Markdown files are supported.")

        with tempfile.NamedTemporaryFile(delete=True, suffix=suffix) as temp:
            while True:
                chunk = await uploaded.read(1024 * 1024)
                if not chunk:
                    break
                temp.write(chunk)
            temp.flush()
            try:
                results.append(ingest_file(Path(temp.name), uploaded.filename or "paper"))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
    return {"results": results}


@app.post("/api/query")
def query(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question is required.")
    return answer(request.question.strip(), max(1, min(request.top_k, 12)))


@app.get("/api/source/{chunk_id}")
def get_source(chunk_id: int):
    result = source(chunk_id)
    if not result:
        raise HTTPException(status_code=404, detail="Source not found.")
    return result
