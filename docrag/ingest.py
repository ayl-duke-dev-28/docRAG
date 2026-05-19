import hashlib
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

from pypdf import PdfReader

from .config import CHUNK_OVERLAP, CHUNK_WORDS, UPLOAD_DIR
from .llm import LLMError, embed_texts
from .storage import add_chunks, create_document, document_by_hash


WHITESPACE_RE = re.compile(r"\s+")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def extract_pages(path: Path) -> List[Tuple[int, str]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            pages.append((index, clean_text(page.extract_text() or "")))
        return pages
    if suffix in {".txt", ".md"}:
        return [(1, clean_text(path.read_text(errors="ignore")))]
    raise ValueError("Only PDF, TXT, and Markdown files are supported.")


def chunk_pages(pages: List[Tuple[int, str]]) -> List[Dict]:
    chunks = []
    words_with_pages = []
    for page_number, text in pages:
        for word in text.split():
            words_with_pages.append((word, page_number))

    if not words_with_pages:
        return []

    start = 0
    chunk_index = 0
    step = max(1, CHUNK_WORDS - CHUNK_OVERLAP)
    while start < len(words_with_pages):
        window = words_with_pages[start : start + CHUNK_WORDS]
        text = " ".join(word for word, _ in window)
        page_numbers = [page for _, page in window]
        chunks.append(
            {
                "chunk_index": chunk_index,
                "page_start": min(page_numbers),
                "page_end": max(page_numbers),
                "text": text,
            }
        )
        chunk_index += 1
        start += step
    return chunks


def ingest_file(temp_path: Path, original_filename: str) -> Dict:
    content_hash = sha256_file(temp_path)
    existing = document_by_hash(content_hash)
    if existing:
        return {
            "status": "duplicate",
            "document_id": existing["id"],
            "filename": existing["filename"],
            "chunks": None,
        }

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_filename).strip("_") or "paper"
    stored_path = UPLOAD_DIR / "{hash}_{name}".format(hash=content_hash[:12], name=safe_name)
    shutil.copyfile(temp_path, stored_path)

    pages = extract_pages(stored_path)
    chunks = chunk_pages(pages)
    if not chunks:
        raise ValueError("No extractable text found in this file.")

    try:
        embeddings = embed_texts([chunk["text"] for chunk in chunks])
    except LLMError as exc:
        raise ValueError(str(exc)) from exc
    if embeddings:
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding

    document_id = create_document(original_filename, stored_path, content_hash, len(pages))
    add_chunks(document_id, original_filename, chunks)

    return {
        "status": "ingested",
        "document_id": document_id,
        "filename": original_filename,
        "chunks": len(chunks),
    }
