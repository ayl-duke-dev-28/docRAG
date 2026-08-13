from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.unit
def test_corpus_and_query_status_regions_are_accessible():
    html = (ROOT / "static" / "index.html").read_text()

    assert 'id="graph-kinds"' in html
    assert 'id="upload-status"' in html
    assert 'id="query-status"' in html
    assert html.count('aria-live="polite"') >= 3


@pytest.mark.unit
def test_ui_renders_corpus_metadata_and_collapsed_source_policy():
    javascript = (ROOT / "static" / "app.js").read_text()

    assert "graph_contribution" in javascript
    assert "source_type" in javascript
    assert 'index < 2 ? " open" : ""' in javascript
    for status in (
        "Searching corpus",
        "Finding graph entities",
        "Walking typed relations",
        "Preparing cited answer",
    ):
        assert status in javascript
