from pathlib import Path
from typing import Dict, List

import pytest

from docrag import sample_corpus


def _fake_ingest(records: List[Dict], status: str = "ingested"):
    def ingest(path: Path, filename: str, *, source_type: str = "upload", **kwargs) -> Dict:
        records.append({"filename": filename, "source_type": source_type})
        return {
            "status": status,
            "document_id": len(records),
            "filename": filename,
            "chunks": None if status == "duplicate" else 3,
        }

    return ingest


@pytest.mark.unit
def test_sample_documents_are_the_checked_in_public_corpus():
    documents = sample_corpus.sample_documents()

    assert documents, "the public corpus ships with the repository"
    assert all(path.suffix == ".md" for path in documents)
    assert [path.name for path in documents] == sorted(path.name for path in documents)


@pytest.mark.unit
def test_loading_the_sample_corpus_tags_documents_as_samples(
    monkeypatch: pytest.MonkeyPatch,
):
    # Arrange
    records: List[Dict] = []
    monkeypatch.setattr(sample_corpus, "ingest_file", _fake_ingest(records))

    # Act
    result = sample_corpus.load_sample_corpus()

    # Assert
    assert result["ingested"] == len(records)
    assert result["duplicates"] == 0
    assert {record["source_type"] for record in records} == {"sample"}


@pytest.mark.unit
def test_loading_an_already_loaded_corpus_counts_duplicates_instead_of_failing(
    monkeypatch: pytest.MonkeyPatch,
):
    records: List[Dict] = []
    monkeypatch.setattr(
        sample_corpus, "ingest_file", _fake_ingest(records, status="duplicate")
    )

    result = sample_corpus.load_sample_corpus()

    assert result["ingested"] == 0
    assert result["duplicates"] == len(records)


@pytest.mark.unit
def test_a_missing_corpus_directory_is_reported_not_silently_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setattr(sample_corpus, "CORPUS_DIR", tmp_path / "absent")

    with pytest.raises(sample_corpus.SampleCorpusError):
        sample_corpus.load_sample_corpus()


@pytest.mark.unit
def test_an_unreadable_document_fails_loudly(monkeypatch: pytest.MonkeyPatch):
    def explode(path: Path, filename: str, **kwargs) -> Dict:
        raise ValueError("No extractable text found in this file.")

    monkeypatch.setattr(sample_corpus, "ingest_file", explode)

    with pytest.raises(sample_corpus.SampleCorpusError) as excinfo:
        sample_corpus.load_sample_corpus()

    assert "No extractable text" in str(excinfo.value)
