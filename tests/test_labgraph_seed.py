import pytest

from labgraph.graph import LabGraph
from labgraph.seed import seed_entities_from_chunks


@pytest.mark.unit
def test_seed_entities_preserves_chunk_rank_and_deduplicates(
    seed_graph: LabGraph,
):
    seeds = seed_entities_from_chunks(seed_graph, [2, "1", 999])

    assert [entity.id for entity in seeds] == [
        "method:curriculum-learning",
        "decision:march-team-sync",
        "person:alex-liu",
        "paper:training-stability-2024",
    ]


@pytest.mark.unit
def test_seed_entities_returns_empty_for_no_matching_chunks(seed_graph: LabGraph):
    assert seed_entities_from_chunks(seed_graph, []) == ()
    assert seed_entities_from_chunks(seed_graph, ["missing"]) == ()
