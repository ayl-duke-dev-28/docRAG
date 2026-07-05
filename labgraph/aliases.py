from pathlib import Path
from typing import Dict, Iterable, Optional

import yaml

from .schema import EntityKind, canonical_id, normalize


class AliasResolver:
    """Resolves surface forms of entity names to canonical IDs.

    Aliases are declared per kind. The resolver normalizes lookups so
    "Alex Liu", "alex liu", and "A. Liu" (if aliased) all collapse to
    the same canonical id.
    """

    def __init__(self) -> None:
        self._by_kind: Dict[EntityKind, Dict[str, str]] = {
            kind: {} for kind in EntityKind
        }

    def add(self, kind: EntityKind, canonical_name: str, aliases: Iterable[str]) -> str:
        canonical = canonical_id(kind, canonical_name)
        self._by_kind[kind][normalize(canonical_name)] = canonical
        for alias in aliases:
            slug = normalize(alias)
            if not slug:
                continue
            self._by_kind[kind][slug] = canonical
        return canonical

    def resolve(self, kind: EntityKind, surface: str) -> str:
        slug = normalize(surface)
        if not slug:
            raise ValueError(f"Cannot resolve empty surface for kind {kind.value}")
        mapped = self._by_kind[kind].get(slug)
        if mapped is not None:
            return mapped
        return f"{kind.value}:{slug}"

    def known_aliases(self, kind: EntityKind, canonical: str) -> tuple:
        return tuple(
            slug for slug, target in self._by_kind[kind].items() if target == canonical
        )

    @classmethod
    def from_yaml(cls, path: Optional[Path]) -> "AliasResolver":
        resolver = cls()
        if path is None or not path.exists():
            return resolver

        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        if not isinstance(raw, dict):
            raise ValueError(f"Alias file must be a mapping at the top level: {path}")

        for kind_str, entries in raw.items():
            try:
                kind = EntityKind(kind_str)
            except ValueError as exc:
                raise ValueError(f"Unknown entity kind in alias file: {kind_str!r}") from exc

            if not isinstance(entries, list):
                raise ValueError(f"Alias entries for {kind_str} must be a list")

            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError(f"Alias entry for {kind_str} must be a mapping")
                canonical = entry.get("canonical")
                aliases = entry.get("aliases", [])
                if not isinstance(canonical, str) or not canonical.strip():
                    raise ValueError(f"Alias entry missing canonical name for {kind_str}")
                if not isinstance(aliases, list):
                    raise ValueError(f"Aliases for {canonical} must be a list")
                resolver.add(kind, canonical, [a for a in aliases if isinstance(a, str)])

        return resolver
