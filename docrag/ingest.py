import hashlib
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pypdf import PdfReader

from labgraph.aliases import AliasResolver
from labgraph.extract import (
    Chunk,
    Extractor,
    OpenAIExtractor,
    RegexExtractor,
    extract_many,
)
from labgraph.storage import load_graph, save_graph

from .config import (
    BASE_DIR,
    CHUNK_OVERLAP,
    CHUNK_WORDS,
    LABGRAPH_DB_PATH,
    LABGRAPH_EXTRACTION_MODEL,
    LABGRAPH_EXTRACTOR,
    OPENAI_API_KEY,
    UPLOAD_DIR,
)
from .llm import LLMError, embed_texts
from .storage import (
    add_chunks,
    chunks_for_document,
    create_document,
    delete_document,
    document_by_hash,
)


WHITESPACE_RE = re.compile(r"\s+")


def build_labgraph_extractor(
    *,
    mode: str = LABGRAPH_EXTRACTOR,
    api_key: str = OPENAI_API_KEY,
    model: str = LABGRAPH_EXTRACTION_MODEL,
    aliases: Optional[AliasResolver] = None,
) -> Extractor:
    """Build the configured graph extractor without making a network call."""
    selected = mode.strip().lower()
    if selected not in {"auto", "regex", "openai"}:
        raise ValueError(
            "LABGRAPH_EXTRACTOR must be one of: auto, regex, openai."
        )
    if selected == "auto":
        selected = "openai" if api_key.strip() else "regex"

    if aliases is None:
        alias_path = BASE_DIR / "labgraph" / "aliases.yaml"
        aliases = (
            AliasResolver.from_yaml(alias_path)
            if alias_path.exists()
            else AliasResolver()
        )

    if selected == "regex":
        return RegexExtractor(aliases=aliases)
    if not api_key.strip():
        raise ValueError(
            "LABGRAPH_EXTRACTOR=openai requires OPENAI_API_KEY."
        )
    return OpenAIExtractor(model=model, aliases=aliases, api_key=api_key)


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
    try:
        update_labgraph_for_document(document_id)
    except Exception as exc:
        delete_document(document_id)
        if stored_path.exists():
            stored_path.unlink()
        raise ValueError(f"Graph extraction failed: {exc}") from exc

    return {
        "status": "ingested",
        "document_id": document_id,
        "filename": original_filename,
        "chunks": len(chunks),
    }


def update_labgraph_for_document(document_id: int) -> None:
    rows = chunks_for_document(document_id)
    if not rows:
        return

    extractor = build_labgraph_extractor()
    result = extract_many(
        extractor,
        [
            Chunk(id=str(row["id"]), filename=row["filename"], text=row["text"])
            for row in rows
        ],
    )

    graph = load_graph(LABGRAPH_DB_PATH)
    for entity in result.entities:
        graph.add_entity(entity)
    for relation in result.relations:
        graph.add_relation(relation)
    save_graph(graph, LABGRAPH_DB_PATH)
