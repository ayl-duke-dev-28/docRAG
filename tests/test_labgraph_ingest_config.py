import pytest

from docrag.ingest import build_labgraph_extractor
from labgraph.extract import OpenAIExtractor, RegexExtractor


@pytest.mark.parametrize(
    ("mode", "api_key", "expected_type"),
    [
        ("auto", "", RegexExtractor),
        ("auto", "sk-test", OpenAIExtractor),
        ("regex", "sk-test", RegexExtractor),
        ("openai", "sk-test", OpenAIExtractor),
    ],
)
def test_build_labgraph_extractor_selects_configured_runtime(
    mode: str, api_key: str, expected_type: type
):
    extractor = build_labgraph_extractor(
        mode=mode,
        api_key=api_key,
        model="gpt-test",
    )

    assert isinstance(extractor, expected_type)
    if isinstance(extractor, OpenAIExtractor):
        assert extractor.model == "gpt-test"


def test_build_labgraph_extractor_requires_a_key_for_explicit_openai():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_labgraph_extractor(mode="openai", api_key="")


def test_build_labgraph_extractor_rejects_an_unknown_mode():
    with pytest.raises(ValueError, match="LABGRAPH_EXTRACTOR"):
        build_labgraph_extractor(mode="local", api_key="")
