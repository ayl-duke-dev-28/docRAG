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


@pytest.mark.unit
def test_mobile_layout_places_query_before_corpus_and_answers():
    stylesheet = (ROOT / "static" / "styles.css").read_text()

    mobile = stylesheet.split("@media (max-width: 820px)", 1)[1]
    assert "order: -1" in mobile
    assert ".query-form" in mobile
    assert "order: -1" in mobile.split(".query-form", 1)[1]


@pytest.mark.unit
def test_entity_browser_controls_are_present_and_labelled():
    html = (ROOT / "static" / "index.html").read_text()

    for element_id in (
        "entity-browser",
        "entity-search",
        "entity-kind",
        "entity-list",
        "entity-count",
    ):
        assert f'id="{element_id}"' in html

    # Every browser control needs a label, visible or screen-reader only.
    assert 'for="entity-search"' in html
    assert 'for="entity-kind"' in html
    assert html.count('aria-live="polite"') >= 4


@pytest.mark.unit
def test_entity_browser_renders_connectivity_and_typed_relations():
    javascript = (ROOT / "static" / "app.js").read_text()

    assert "/api/labgraph/entities" in javascript
    assert "relation_count" in javascript
    assert "entity_name" in javascript
    assert "direction" in javascript
    # Empty and unavailable states both need a next action, not a blank list.
    assert "No entities match" in javascript
    assert "No graph entities yet" in javascript


@pytest.mark.unit
def test_entity_browser_escapes_graph_supplied_text():
    javascript = (ROOT / "static" / "app.js").read_text()

    browser = javascript.split("function renderEntityBrowser", 1)[1].split(
        "async function loadEntities", 1
    )[0]
    for interpolation in ("entity.name", "relation.entity_name", "entity.kind"):
        assert f"escapeHtml({interpolation})" in browser
