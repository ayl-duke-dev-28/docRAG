import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

from .aliases import AliasResolver
from .schema import Entity, EntityKind, Relation, RelationKind, canonical_id


@dataclass(frozen=True)
class Chunk:
    """A minimal document chunk the extractor operates on.

    Independent of docrag's storage row shape so tests do not need SQLite.
    """
    id: str
    filename: str
    text: str


@dataclass(frozen=True)
class ExtractionResult:
    entities: Tuple[Entity, ...] = field(default_factory=tuple)
    relations: Tuple[Relation, ...] = field(default_factory=tuple)


class Extractor(Protocol):
    """Contract every extractor implementation must satisfy."""

    name: str

    def extract(self, chunk: Chunk) -> ExtractionResult: ...


# ---- deterministic baseline extractor -------------------------------

_PERSON_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b")
_METHOD_RE = re.compile(r"\b((?:curriculum learning|gradient clipping|qLoRA|LoRA|RLHF|method [A-Z]))\b", re.IGNORECASE)
_PROJECT_RE = re.compile(r"\bProject\s+([A-Z][A-Za-z0-9]+)\b")
_DECISION_RE = re.compile(
    r"\b("
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+team\s+sync"
    r"|weekly\s+standup"
    r"|planning\s+meeting"
    r")\b",
    re.IGNORECASE,
)


class RegexExtractor:
    """A deterministic, dependency-free extractor for tests and CI.

    Recognizes a small fixed vocabulary of methods and a person-name shape.
    Not intended to be accurate on real papers; intended to make the graph
    pipeline testable end-to-end without any LLM call. The OpenAI extractor
    replaces this at runtime.
    """

    name = "regex"

    def __init__(self, aliases: Optional[AliasResolver] = None) -> None:
        self._aliases = aliases or AliasResolver()

    def extract(self, chunk: Chunk) -> ExtractionResult:
        text = chunk.text
        entities: Dict[str, Entity] = {}
        relations: List[Relation] = []
        provenance = (chunk.id,)

        for match in _PERSON_RE.finditer(text):
            name = match.group(1)
            entity_id = self._resolve(EntityKind.PERSON, name)
            entities.setdefault(
                entity_id,
                Entity(id=entity_id, kind=EntityKind.PERSON, name=name),
            )

        for match in _METHOD_RE.finditer(text):
            name = match.group(1)
            entity_id = self._resolve(EntityKind.METHOD, name)
            entities.setdefault(
                entity_id,
                Entity(id=entity_id, kind=EntityKind.METHOD, name=name.strip()),
            )

        for match in _PROJECT_RE.finditer(text):
            name = "Project " + match.group(1)
            entity_id = self._resolve(EntityKind.PROJECT, name)
            entities.setdefault(
                entity_id,
                Entity(id=entity_id, kind=EntityKind.PROJECT, name=name),
            )

        for match in _DECISION_RE.finditer(text):
            name = match.group(1)
            entity_id = self._resolve(EntityKind.DECISION, name)
            entities.setdefault(
                entity_id,
                Entity(
                    id=entity_id,
                    kind=EntityKind.DECISION,
                    name=name,
                    attrs=(("source_filename", chunk.filename),),
                ),
            )

        # Every chunk sourced from a filename ending in .pdf gets a Paper
        # entity representing the document itself; papers are first-class
        # graph citizens per the design.
        paper = self._paper_from_chunk(chunk)
        if paper is not None:
            entities.setdefault(paper.id, paper)

        # Relations we can infer without semantics:
        # - person -> paper: authored (if paper exists in this chunk)
        # - paper  -> method: uses_method
        # - method -> decision: decided_in
        person_ids = [eid for eid, e in entities.items() if e.kind == EntityKind.PERSON]
        method_ids = [eid for eid, e in entities.items() if e.kind == EntityKind.METHOD]
        decision_ids = [eid for eid, e in entities.items() if e.kind == EntityKind.DECISION]

        if paper is not None:
            for person_id in person_ids:
                relations.append(
                    Relation(
                        source_id=person_id,
                        target_id=paper.id,
                        kind=RelationKind.AUTHORED,
                        provenance=provenance,
                    )
                )
            for method_id in method_ids:
                relations.append(
                    Relation(
                        source_id=paper.id,
                        target_id=method_id,
                        kind=RelationKind.USES_METHOD,
                        provenance=provenance,
                    )
                )

        for method_id in method_ids:
            for decision_id in decision_ids:
                relations.append(
                    Relation(
                        source_id=method_id,
                        target_id=decision_id,
                        kind=RelationKind.DECIDED_IN,
                        provenance=provenance,
                    )
                )

        return ExtractionResult(
            entities=tuple(entities.values()),
            relations=tuple(relations),
        )

    def _resolve(self, kind: EntityKind, surface: str) -> str:
        return self._aliases.resolve(kind, surface)

    @staticmethod
    def _paper_from_chunk(chunk: Chunk) -> Optional[Entity]:
        filename = (chunk.filename or "").strip()
        if not filename:
            return None
        lower = filename.lower()
        # Every ingested document becomes a Paper entity keyed on filename,
        # regardless of extension. Meeting notes are also modelled as Paper
        # entities so the graph can bridge formal and informal artefacts.
        stem = re.sub(r"\.[a-z0-9]+$", "", filename)
        entity_id = canonical_id(EntityKind.PAPER, stem)
        attrs: Tuple[Tuple[str, str], ...] = (
            ("source_filename", filename),
            ("format", _classify_source(lower)),
        )
        return Entity(
            id=entity_id,
            kind=EntityKind.PAPER,
            name=stem,
            attrs=attrs,
        )


def _classify_source(filename_lower: str) -> str:
    if filename_lower.endswith(".pdf"):
        return "paper"
    if filename_lower.endswith((".docx", ".doc", ".md")):
        return "meeting_note"
    return "unknown"


# ---- LLM extractor stub ---------------------------------------------


class OpenAIExtractor:
    """Placeholder for the real LLM extractor.

    Kept as a stub so the runtime interface exists and the graph builder can
    switch implementations by name. The real implementation lands in the next
    slice and issues one structured-outputs call per chunk.
    """

    name = "openai"

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model

    def extract(self, chunk: Chunk) -> ExtractionResult:
        raise NotImplementedError(
            "OpenAIExtractor is not implemented yet. "
            "Use RegexExtractor for CI and tests; the OpenAI implementation lands next."
        )


# ---- convenience -----------------------------------------------------


def extract_many(
    extractor: Extractor, chunks: Sequence[Chunk]
) -> ExtractionResult:
    """Run an extractor over multiple chunks and merge the result."""
    entities: Dict[str, Entity] = {}
    relations: List[Relation] = []
    for chunk in chunks:
        result = extractor.extract(chunk)
        for entity in result.entities:
            entities.setdefault(entity.id, entity)
        relations.extend(result.relations)
    return ExtractionResult(
        entities=tuple(entities.values()),
        relations=tuple(relations),
    )
