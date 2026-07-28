import logging
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from docrag.config import (
    BASE_DIR,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_REDIRECT_URI,
    LABGRAPH_DB_PATH,
    UPLOAD_DIR,
)
from docrag.google_drive import (
    CredentialsStore,
    GoogleDriveConnector,
    GoogleDriveError,
)
from docrag.ingest import ingest_file
from docrag.retrieval import answer, source
from docrag.storage import delete_document, get_document, init_db, list_documents, rename_document
from labgraph.schema import Entity, EntityKind
from labgraph.storage import load_graph
from labgraph.trace import (
    DEFAULT_MAX_DEPTH,
    QuestionTrace,
    TraceStatus,
    trace_between,
    trace_for_question,
)

logger = logging.getLogger(__name__)
google_drive_connector = GoogleDriveConnector(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    redirect_uri=GOOGLE_REDIRECT_URI,
    credentials_store=CredentialsStore(GOOGLE_CREDENTIALS_PATH),
)

MAX_TRACE_DEPTH = 8
MAX_TOP_K = 12

app = FastAPI(title="LabGraph", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class QueryRequest(BaseModel):
    question: str
    top_k: int = 6


class RenameDocumentRequest(BaseModel):
    filename: str


class GoogleDriveImportRequest(BaseModel):
    document_ids: List[str]


class QueryTraceRequest(BaseModel):
    question: Optional[str] = None
    source_id: Optional[str] = None
    target_id: Optional[str] = None
    max_depth: int = DEFAULT_MAX_DEPTH


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


def google_document_filename(name: str) -> str:
    cleaned = re.sub(r"[/\\\\]+", " - ", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned) or "Google Doc"
    return cleaned if cleaned.lower().endswith(".md") else f"{cleaned}.md"


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/documents")
def documents():
    return [dict(row) for row in list_documents()]


@app.get("/api/google-drive/status")
def google_drive_status():
    return google_drive_connector.status()


@app.get("/api/google-drive/connect")
def google_drive_connect():
    try:
        return {
            "authorization_url": google_drive_connector.start_authorization()
        }
    except GoogleDriveError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/google-drive/callback")
def google_drive_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Google Drive authorization was denied: {error}",
        )
    try:
        google_drive_connector.finish_authorization(
            code=code or "",
            state=state or "",
        )
    except GoogleDriveError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/?google_drive=connected", status_code=303)


@app.delete("/api/google-drive/connection")
def google_drive_disconnect():
    google_drive_connector.disconnect()
    return {"status": "disconnected"}


@app.get("/api/google-drive/documents")
def google_drive_documents():
    try:
        documents = google_drive_connector.list_documents()
    except GoogleDriveError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"documents": [document.as_dict() for document in documents]}


@app.post("/api/google-drive/import")
def google_drive_import(request: GoogleDriveImportRequest):
    document_ids = tuple(
        dict.fromkeys(
            document_id.strip()
            for document_id in request.document_ids
            if document_id.strip()
        )
    )
    if not document_ids:
        raise HTTPException(
            status_code=400,
            detail="Select at least one Google Doc to import.",
        )
    if len(document_ids) > 25:
        raise HTTPException(
            status_code=400,
            detail="Import at most 25 Google Docs at a time.",
        )

    results = []
    for document_id in document_ids:
        try:
            exported = google_drive_connector.download_document(document_id)
            filename = google_document_filename(exported.document.name)
            with tempfile.NamedTemporaryFile(
                mode="w+",
                encoding="utf-8",
                delete=True,
                suffix=".md",
            ) as temp:
                temp.write(exported.text)
                temp.flush()
                result = ingest_file(Path(temp.name), filename)
        except GoogleDriveError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        results.append(
            {
                **result,
                "source": {
                    "provider": "google_drive",
                    "document_id": exported.document.id,
                },
            }
        )
    return {"results": results}


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
        "aliases": list(entity.aliases),
        "attrs": entity.as_attrs_dict(),
    }


def compact_relation(relation) -> Dict:
    return {
        "source_id": relation.source_id,
        "target_id": relation.target_id,
        "kind": relation.kind.value,
        "provenance": list(relation.provenance),
        "attrs": relation.as_attrs_dict(),
    }


def trace_to_dict(result: QuestionTrace) -> Dict:
    return {
        "status": result.status.value,
        "found": result.status is TraceStatus.FOUND,
        "max_depth": result.max_depth,
        "matched": [compact_entity(entity) for entity in result.matched],
        "trace": [entity.name for entity in result.path],
        "path": [compact_entity(entity) for entity in result.path],
        "relations": [compact_relation(relation) for relation in result.relations],
        "neighborhood": [compact_entity(entity) for entity in result.neighborhood],
    }


def question_trace(question: str, graph=None) -> Dict:
    """Build the trace for a question, degrading to an error state.

    A graph failure must never cost the user an answer that retrieval already
    produced, so this reports the failure in the trace instead of raising.
    """
    try:
        if graph is None:
            graph = load_graph(LABGRAPH_DB_PATH)
        return trace_to_dict(trace_for_question(graph, question))
    except Exception:
        logger.exception("Graph trace failed for question")
        return trace_to_dict(QuestionTrace(status=TraceStatus.ERROR))


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
    max_depth = max(1, min(request.max_depth, MAX_TRACE_DEPTH))

    question = (request.question or "").strip()
    if question:
        return trace_to_dict(trace_for_question(graph, question, max_depth=max_depth))
    if request.source_id and request.target_id:
        return trace_to_dict(
            trace_between(graph, request.source_id, request.target_id, max_depth=max_depth)
        )
    raise HTTPException(
        status_code=400,
        detail="Provide a question, or both source_id and target_id.",
    )


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
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")
    top_k = max(1, min(request.top_k, MAX_TOP_K))
    try:
        graph = load_graph(LABGRAPH_DB_PATH)
    except Exception:
        logger.exception("Graph load failed for question")
        result = answer(question, top_k)
        trace = trace_to_dict(QuestionTrace(status=TraceStatus.ERROR))
    else:
        result = answer(question, top_k, graph=graph)
        trace = question_trace(question, graph)
    return {**result, "trace": trace}


@app.get("/api/source/{chunk_id}")
def get_source(chunk_id: int):
    result = source(chunk_id)
    if not result:
        raise HTTPException(status_code=404, detail="Source not found.")
    return result
