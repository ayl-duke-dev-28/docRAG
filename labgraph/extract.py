import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from .aliases import AliasResolver
from .extraction_schema import StructuredExtraction
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


# ---- LLM extractor --------------------------------------------------


class OpenAIExtractionError(RuntimeError):
    """Raised when a chunk cannot be converted from an OpenAI response."""


_EXTRACTION_PROMPT = """\
Extract a typed knowledge graph from exactly one research-document chunk.

Return only entities and relations explicitly supported by the text. Use the
five entity kinds and six relation kinds defined by the response schema. Give
each entity a short local key that is unique within this response, and refer to
those keys from relations. Include the source document itself as a paper
entity when the filename identifies a document. Use empty arrays when nothing
relevant is present. Do not invent provenance; the application attaches the
chunk identifier after validation.
"""


class OpenAIExtractor:
    """Extract typed graph objects with one structured-output call per chunk."""

    name = "openai"

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        client: Optional[Any] = None,
        aliases: Optional[AliasResolver] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.model = model
        self._client = client if client is not None else OpenAI(api_key=api_key)
        self._aliases = aliases or AliasResolver()

    def extract(self, chunk: Chunk) -> ExtractionResult:
        try:
            response = self._client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": _EXTRACTION_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Filename: {chunk.filename}\n"
                            f"Chunk ID: {chunk.id}\n\n"
                            f"Text:\n{chunk.text}"
                        ),
                    },
                ],
                text_format=StructuredExtraction,
            )
        except ValidationError as exc:
            raise OpenAIExtractionError(
                f"OpenAI returned invalid structured output: {exc}"
            ) from exc
        except OpenAIError as exc:
            raise OpenAIExtractionError(
                f"OpenAI extraction request failed: {exc}"
            ) from exc

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            refusal = _response_refusal(response)
            if refusal:
                raise OpenAIExtractionError(f"OpenAI refused extraction: {refusal}")
            raise OpenAIExtractionError("OpenAI response contained no parsed output")

        if not isinstance(parsed, StructuredExtraction):
            try:
                parsed = StructuredExtraction.model_validate(parsed)
            except ValidationError as exc:
                raise OpenAIExtractionError(
                    f"OpenAI returned invalid structured output: {exc}"
                ) from exc

        return self._to_graph_result(parsed, chunk)

    def _to_graph_result(
        self, parsed: StructuredExtraction, chunk: Chunk
    ) -> ExtractionResult:
        entities: Dict[str, Entity] = {}
        ids_by_key: Dict[str, str] = {}

        for extracted in parsed.entities:
            entity_id = self._aliases.resolve(extracted.kind, extracted.name)
            ids_by_key[extracted.key] = entity_id
            attrs = dict((item.key, item.value) for item in extracted.attributes)
            if chunk.filename:
                attrs["source_filename"] = chunk.filename
            aliases = tuple(
                dict.fromkeys(
                    alias
                    for alias in extracted.aliases
                    if alias and alias != extracted.name
                )
            )
            candidate = Entity(
                id=entity_id,
                kind=extracted.kind,
                name=extracted.name,
                aliases=aliases,
                attrs=tuple(attrs.items()),
            )
            entities[entity_id] = _merge_entity(entities.get(entity_id), candidate)

        relations = []
        for extracted in parsed.relations:
            try:
                relation = Relation(
                    source_id=ids_by_key[extracted.source_key],
                    target_id=ids_by_key[extracted.target_key],
                    kind=extracted.kind,
                    provenance=(chunk.id,),
                    attrs=tuple(
                        (item.key, item.value) for item in extracted.attributes
                    ),
                )
            except (KeyError, ValueError) as exc:
                raise OpenAIExtractionError(
                    f"Validated extraction could not be converted: {exc}"
                ) from exc
            relations.append(relation)

        return ExtractionResult(
            entities=tuple(entities.values()),
            relations=tuple(relations),
        )


def _merge_entity(existing: Optional[Entity], candidate: Entity) -> Entity:
    if existing is None:
        return candidate

    aliases = tuple(
        dict.fromkeys(
            existing.aliases
            + (candidate.name,)
            + candidate.aliases
        )
    )
    attrs = dict(existing.attrs)
    attrs.update(candidate.attrs)
    return Entity(
        id=existing.id,
        kind=existing.kind,
        name=existing.name,
        aliases=aliases,
        attrs=tuple(attrs.items()),
    )


def _response_refusal(response: Any) -> Optional[str]:
    for item in getattr(response, "output", ()) or ():
        for content in getattr(item, "content", ()) or ():
            if getattr(content, "type", None) == "refusal":
                refusal = getattr(content, "refusal", None)
                if refusal:
                    return str(refusal)
    return None


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
