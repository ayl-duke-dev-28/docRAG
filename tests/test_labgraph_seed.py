import pytest

from labgraph.graph import LabGraph
from labgraph.seed import expand_chunk_seed_neighborhood, seed_entities_from_chunks


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


@pytest.mark.unit
def test_expand_chunk_seeds_walks_both_directions_with_seeds_first(
    seed_graph: LabGraph,
):
    entities = expand_chunk_seed_neighborhood(seed_graph, [2], max_depth=1)

    assert [entity.id for entity in entities] == [
        "method:curriculum-learning",
        "decision:march-team-sync",
        "paper:training-stability-2024",
    ]


@pytest.mark.unit
def test_expand_chunk_seeds_respects_zero_depth_and_unknown_chunks(
    seed_graph: LabGraph,
):
    seeds_only = expand_chunk_seed_neighborhood(seed_graph, [2], max_depth=0)

    assert [entity.id for entity in seeds_only] == [
        "method:curriculum-learning",
        "decision:march-team-sync",
    ]
    assert expand_chunk_seed_neighborhood(seed_graph, ["missing"], max_depth=2) == ()
