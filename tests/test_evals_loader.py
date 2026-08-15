from pathlib import Path

import pytest

from evals.loader import load_questions


VALID_YAML = """
version: 1
questions:
  - id: q001
    question: What crossed the paper and the meeting?
    expected_entities:
      - curriculum learning
      - gradient clipping
    expected_sources:
      - paper: training_stability_2024.pdf
      - meeting_note: 2024-03-14.docx
    min_distinct_sources: 2
    tags: [multi-hop]
    notes: |
      A sample question.
"""


@pytest.mark.unit
def test_loads_valid_yaml(tmp_path: Path):
    path = tmp_path / "questions.yaml"
    path.write_text(VALID_YAML)

    questions = load_questions(path)

    assert len(questions) == 1
    q = questions[0]
    assert q.id == "q001"
    assert q.expected_entities == ("curriculum learning", "gradient clipping")
    assert [s.filename for s in q.expected_sources] == [
        "training_stability_2024.pdf",
        "2024-03-14.docx",
    ]
    assert [s.kind for s in q.expected_sources] == ["paper", "meeting_note"]
    assert q.tags == ("multi-hop",)


@pytest.mark.unit
def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_questions(tmp_path / "nope.yaml")


@pytest.mark.unit
def test_unsupported_version_raises(tmp_path: Path):
    path = tmp_path / "q.yaml"
    path.write_text("version: 99\nquestions: []\n")
    with pytest.raises(ValueError, match="Unsupported"):
        load_questions(path)


@pytest.mark.unit
def test_empty_questions_raises(tmp_path: Path):
    path = tmp_path / "q.yaml"
    path.write_text("version: 1\nquestions: []\n")
    with pytest.raises(ValueError, match="non-empty"):
        load_questions(path)


@pytest.mark.unit
def test_question_without_id_raises(tmp_path: Path):
    path = tmp_path / "q.yaml"
    path.write_text(
        """
version: 1
questions:
  - question: hi
    expected_sources:
      - paper: a.pdf
"""
    )
    with pytest.raises(ValueError, match="id"):
        load_questions(path)


@pytest.mark.unit
def test_question_without_sources_raises(tmp_path: Path):
    path = tmp_path / "q.yaml"
    path.write_text(
        """
version: 1
questions:
  - id: q1
    question: hi
"""
    )
    with pytest.raises(ValueError, match="expected_source"):
        load_questions(path)


@pytest.mark.unit
def test_string_source_shorthand(tmp_path: Path):
    path = tmp_path / "q.yaml"
    path.write_text(
        """
version: 1
questions:
  - id: q1
    question: hi
    expected_sources:
      - a.pdf
      - b.docx
"""
    )
    questions = load_questions(path)
    assert [s.filename for s in questions[0].expected_sources] == ["a.pdf", "b.docx"]
    assert all(s.kind == "unspecified" for s in questions[0].expected_sources)


@pytest.mark.unit
def test_bundled_questions_file_is_valid():
    root = Path(__file__).resolve().parents[1]
    path = root / "evals" / "questions.yaml"
    questions = load_questions(path)
    corpus = root / "examples" / "public_corpus"

    assert len(questions) == 20
    for q in questions:
        assert q.expected_sources, f"question {q.id} missing expected_sources"
        assert len({source.kind for source in q.expected_sources}) >= 2
        assert "EXAMPLE" not in q.tags
        for source in q.expected_sources:
            assert (corpus / source.filename).is_file(), (
                f"question {q.id} references missing corpus file {source.filename}"
            )


@pytest.mark.unit
def test_graph_lift_challenge_is_small_and_source_backed():
    root = Path(__file__).resolve().parents[1]
    questions = load_questions(root / "evals" / "challenge_questions.yaml")
    corpus = root / "examples" / "public_corpus"

    assert len(questions) == 5
    for question in questions:
        assert "graph-lift" in question.tags
        assert question.min_distinct_sources == 2
        assert len(question.expected_sources) == 2
        assert all(
            (corpus / source.filename).is_file()
            for source in question.expected_sources
        )
