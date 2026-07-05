from pathlib import Path

import pytest

from labgraph.aliases import AliasResolver
from labgraph.schema import EntityKind


@pytest.mark.unit
def test_resolver_falls_back_to_canonical_form_for_unknown():
    resolver = AliasResolver()
    assert resolver.resolve(EntityKind.PERSON, "Unknown Person") == "person:unknown-person"


@pytest.mark.unit
def test_resolver_collapses_aliases_to_canonical():
    resolver = AliasResolver()
    resolver.add(EntityKind.PERSON, "Alex Liu", ["A. Liu", "aliu@duke.edu"])

    assert resolver.resolve(EntityKind.PERSON, "Alex Liu") == "person:alex-liu"
    assert resolver.resolve(EntityKind.PERSON, "A. Liu") == "person:alex-liu"
    assert resolver.resolve(EntityKind.PERSON, "aliu@duke.edu") == "person:alex-liu"


@pytest.mark.unit
def test_resolver_is_kind_isolated():
    resolver = AliasResolver()
    resolver.add(EntityKind.PERSON, "Atlas", [])
    resolver.add(EntityKind.PROJECT, "Project Atlas", ["Atlas"])

    assert resolver.resolve(EntityKind.PERSON, "Atlas") == "person:atlas"
    assert resolver.resolve(EntityKind.PROJECT, "Atlas") == "project:project-atlas"


@pytest.mark.unit
def test_resolver_rejects_empty_lookup():
    resolver = AliasResolver()
    with pytest.raises(ValueError, match="empty surface"):
        resolver.resolve(EntityKind.METHOD, "   ")


@pytest.mark.unit
def test_from_yaml_missing_file_returns_empty_resolver(tmp_path: Path):
    resolver = AliasResolver.from_yaml(tmp_path / "missing.yaml")
    # unknown lookups still resolve via the fallback path
    assert resolver.resolve(EntityKind.PERSON, "Alex Liu") == "person:alex-liu"


@pytest.mark.unit
def test_from_yaml_reads_starter_file():
    root = Path(__file__).resolve().parents[1]
    resolver = AliasResolver.from_yaml(root / "labgraph" / "aliases.yaml")

    assert resolver.resolve(EntityKind.METHOD, "qLoRA") == "method:qlora"
    assert resolver.resolve(EntityKind.METHOD, "quantized LoRA") == "method:qlora"
    assert resolver.resolve(EntityKind.PERSON, "A. Liu") == "person:alex-liu"


@pytest.mark.unit
def test_from_yaml_rejects_unknown_kind(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text("mystery:\n  - canonical: Foo\n    aliases: []\n")
    with pytest.raises(ValueError, match="Unknown entity kind"):
        AliasResolver.from_yaml(path)


@pytest.mark.unit
def test_from_yaml_rejects_bad_entry_shape(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text("person: not-a-list\n")
    with pytest.raises(ValueError, match="must be a list"):
        AliasResolver.from_yaml(path)


@pytest.mark.unit
def test_from_yaml_rejects_bad_top_level(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text("- just a list\n")
    with pytest.raises(ValueError, match="mapping"):
        AliasResolver.from_yaml(path)


@pytest.mark.unit
def test_known_aliases_lists_all_slugs_pointing_at_canonical():
    resolver = AliasResolver()
    canonical = resolver.add(EntityKind.PERSON, "Alex Liu", ["A. Liu"])
    known = resolver.known_aliases(EntityKind.PERSON, canonical)
    assert "alex-liu" in known
    assert "a-liu" in known
