import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Tuple


class EntityKind(str, Enum):
    PERSON = "person"
    PROJECT = "project"
    METHOD = "method"
    PAPER = "paper"
    DECISION = "decision"


class RelationKind(str, Enum):
    AUTHORED = "authored"          # Person -> Paper
    MENTIONS = "mentions"          # Paper|Decision -> anything
    USES_METHOD = "uses_method"    # Paper|Project -> Method
    SUPERSEDES = "supersedes"      # Method -> Method (later replaces earlier)
    DECIDED_IN = "decided_in"      # Method|Project -> Decision
    WORKS_ON = "works_on"          # Person -> Project


_NON_ID_RE = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    lowered = text.strip().lower()
    slug = _NON_ID_RE.sub("-", lowered).strip("-")
    return slug


def canonical_id(kind: EntityKind, name: str) -> str:
    slug = normalize(name)
    if not slug:
        raise ValueError(f"Cannot build canonical id from empty name for kind {kind.value}")
    return f"{kind.value}:{slug}"


@dataclass(frozen=True)
class Entity:
    id: str
    kind: EntityKind
    name: str
    aliases: Tuple[str, ...] = ()
    attrs: Tuple[Tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Entity.id must be non-empty")
        if not self.name:
            raise ValueError("Entity.name must be non-empty")
        expected_prefix = f"{self.kind.value}:"
        if not self.id.startswith(expected_prefix):
            raise ValueError(
                f"Entity.id {self.id!r} must start with {expected_prefix!r}"
            )

    def as_attrs_dict(self) -> Dict[str, str]:
        return {key: value for key, value in self.attrs}

    def with_alias(self, alias: str) -> "Entity":
        stripped = alias.strip()
        if not stripped or stripped in self.aliases or stripped == self.name:
            return self
        return Entity(
            id=self.id,
            kind=self.kind,
            name=self.name,
            aliases=self.aliases + (stripped,),
            attrs=self.attrs,
        )


@dataclass(frozen=True)
class Relation:
    source_id: str
    target_id: str
    kind: RelationKind
    provenance: Tuple[str, ...] = field(default_factory=tuple)
    attrs: Tuple[Tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.source_id == self.target_id:
            raise ValueError(
                f"Self-loop relation not allowed: {self.source_id} -[{self.kind.value}]-> {self.target_id}"
            )

    def as_attrs_dict(self) -> Dict[str, str]:
        return {key: value for key, value in self.attrs}
