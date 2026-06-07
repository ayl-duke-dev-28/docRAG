import tempfile
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from docrag.config import BASE_DIR, UPLOAD_DIR
from docrag.ingest import ingest_file
from docrag.retrieval import answer, source
from docrag.storage import delete_document, get_document, init_db, list_documents, rename_document


app = FastAPI(title="docRAG", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class QueryRequest(BaseModel):
    question: str
    top_k: int = 6


class RenameDocumentRequest(BaseModel):
    filename: str


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
