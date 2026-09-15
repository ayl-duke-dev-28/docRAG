"""Load the checked-in public corpus so a new install has something to ask about.

``scripts/seed_public_corpus.py`` builds a fresh demo database offline; this
module ingests the same documents into the running instance, which is what the
empty-library onboarding button calls.
"""

from pathlib import Path
from typing import Dict, List

from .config import BASE_DIR
from .ingest import ingest_file

CORPUS_DIR = BASE_DIR / "examples" / "public_corpus"
SAMPLE_SOURCE_TYPE = "sample"


class SampleCorpusError(RuntimeError):
    """The sample corpus could not be loaded."""


def sample_documents() -> List[Path]:
    """Return the corpus documents in a stable order."""
    if not CORPUS_DIR.is_dir():
        return []
    return sorted(CORPUS_DIR.glob("*.md"))


def load_sample_corpus() -> Dict:
    """Ingest every sample document, reporting what was new and what existed.

    Re-running is safe: ingestion deduplicates by content hash, so a second
    call counts duplicates rather than creating copies.
    """
    documents = sample_documents()
    if not documents:
        raise SampleCorpusError(
            "Sample corpus is missing from this install. "
            "Expected Markdown documents in examples/public_corpus."
        )

    ingested = 0
    duplicates = 0
    filenames: List[str] = []
    for document in documents:
        try:
            result = ingest_file(
                document,
                document.name,
                source_type=SAMPLE_SOURCE_TYPE,
            )
        except (OSError, ValueError) as exc:
            raise SampleCorpusError(
                f"Could not load {document.name}: {exc}"
            ) from exc

        if result["status"] == "duplicate":
            duplicates += 1
        else:
            ingested += 1
        filenames.append(result["filename"])

    return {"ingested": ingested, "duplicates": duplicates, "documents": filenames}
