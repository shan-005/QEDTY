from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from seraph.core.enums import EntityType, EventType, RelationshipType

if TYPE_CHECKING:
    from collections.abc import Mapping

ONTOLOGY_VERSION: Final[str] = "2.0.0"
ONTOLOGY_PROFILE: Final[str] = f"seraph-ontology@{ONTOLOGY_VERSION}"
WORLD_MODEL_SCHEMA: Final[str] = "seraph-world-model@1.0.0"
SERAPH_NAMESPACE: Final[str] = "https://seraph.local/ontology/"
SERAPH_CONTEXT: Final[str] = "https://seraph.local/ontology/context.jsonld"

RDF_NAMESPACE: Final[str] = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NAMESPACE: Final[str] = "http://www.w3.org/2000/01/rdf-schema#"
OWL_NAMESPACE: Final[str] = "http://www.w3.org/2002/07/owl#"
SHACL_NAMESPACE: Final[str] = "http://www.w3.org/ns/shacl#"
PROV_NAMESPACE: Final[str] = "http://www.w3.org/ns/prov#"
SOSA_NAMESPACE: Final[str] = "http://www.w3.org/ns/sosa/"
SSN_NAMESPACE: Final[str] = "http://www.w3.org/ns/ssn/"
SKOS_NAMESPACE: Final[str] = "http://www.w3.org/2004/02/skos/core#"
DCAT_NAMESPACE: Final[str] = "http://www.w3.org/ns/dcat#"
DCTERMS_NAMESPACE: Final[str] = "http://purl.org/dc/terms/"
GEOSPARQL_NAMESPACE: Final[str] = "http://www.opengis.net/ont/geosparql#"
XSD_NAMESPACE: Final[str] = "http://www.w3.org/2001/XMLSchema#"

_NAMESPACES: Mapping[str, str] = MappingProxyType(
    {
        "seraph": SERAPH_NAMESPACE,
        "rdf": RDF_NAMESPACE,
        "rdfs": RDFS_NAMESPACE,
        "owl": OWL_NAMESPACE,
        "sh": SHACL_NAMESPACE,
        "prov": PROV_NAMESPACE,
        "sosa": SOSA_NAMESPACE,
        "ssn": SSN_NAMESPACE,
        "skos": SKOS_NAMESPACE,
        "dcat": DCAT_NAMESPACE,
        "dcterms": DCTERMS_NAMESPACE,
        "geo": GEOSPARQL_NAMESPACE,
        "xsd": XSD_NAMESPACE,
    }
)

STANDARDS_BASELINE: Mapping[str, str] = MappingProxyType(
    {
        "rdf": "RDF 1.1 Recommendation; RDF 1.2 Candidate Recommendation monitored",
        "owl": "OWL 2 Recommendation",
        "shacl": "SHACL Recommendation 2017; SHACL 1.2 Working Draft monitored",
        "prov": "PROV-O Recommendation",
        "ssn": "SSN 2023 Recommendation / OGC Standard",
        "geosparql": "GeoSPARQL 1.1 OGC Standard",
        "skos": "SKOS Recommendation",
        "dcat": "DCAT 3 Recommendation",
    }
)

_IRI_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:[^\s]+$")


@dataclass(frozen=True, slots=True)
class OntologyTerm:
    """Stable semantic term descriptor at the Python/standards boundary."""

    name: str
    iri: str
    kind: str
    definition: str
    parent_iri: str | None = None


def namespaces() -> Mapping[str, str]:
    """Return an immutable prefix-to-namespace mapping."""
    return _NAMESPACES


def iri(local_name: str) -> str:
    """Build a SERAPH IRI for a local ontology term."""
    normalized = local_name.strip()
    if not normalized or any(ch.isspace() for ch in normalized):
        raise ValueError("local ontology term must be non-blank and whitespace-free")
    return f"{SERAPH_NAMESPACE}{normalized}"


def normalize_text(value: str, *, casefold: bool = False, max_length: int = 4096) -> str:
    """Normalize human text without collapsing semantic punctuation."""
    normalized = unicodedata.normalize("NFKC", value).strip()
    normalized = " ".join(normalized.split())
    if casefold:
        normalized = normalized.casefold()
    if not normalized:
        raise ValueError("text must not be blank")
    if len(normalized) > max_length:
        raise ValueError(f"text exceeds maximum length of {max_length}")
    return normalized


def normalize_iri(value: str) -> str:
    """Validate an absolute IRI used as an ontology type or predicate."""
    candidate = normalize_text(value)
    if not _IRI_RE.fullmatch(candidate):
        raise ValueError(f"invalid absolute IRI: {value!r}")
    return candidate


CLASS_IRIS: Mapping[str, str] = MappingProxyType(
    {
        "Entity": iri("Entity"),
        "Relationship": iri("Relationship"),
        "Event": iri("Event"),
        "Capability": iri("Capability"),
        "Service": iri("Service"),
        "Flow": iri("Flow"),
        "Assertion": iri("Assertion"),
        "EntityResolution": iri("EntityResolution"),
        "ExternalIdentifier": iri("ExternalIdentifier"),
        "TimeWindow": iri("TimeWindow"),
        "Quantity": iri("Quantity"),
        "GeodeticPoint": iri("GeodeticPoint"),
    }
)

PROPERTY_IRIS: Mapping[str, str] = MappingProxyType(
    {
        "entityId": iri("entityId"),
        "entityType": iri("entityType"),
        "canonicalName": iri("canonicalName"),
        "description": iri("description"),
        "externalIdentifier": iri("externalIdentifier"),
        "ontologyType": iri("ontologyType"),
        "lifecycle": iri("lifecycle"),
        "location": iri("location"),
        "subject": iri("subject"),
        "object": iri("object"),
        "predicate": iri("predicate"),
        "source": iri("source"),
        "target": iri("target"),
        "relationshipType": iri("relationshipType"),
        "validTime": iri("validTime"),
        "observedAt": iri("observedAt"),
        "assertedAt": iri("assertedAt"),
        "eventType": iri("eventType"),
        "severity": iri("severity"),
        "impactFraction": iri("impactFraction"),
        "phase": iri("phase"),
        "capabilityKind": iri("capabilityKind"),
        "nominalCapacity": iri("nominalCapacity"),
        "minimumCapacity": iri("minimumCapacity"),
        "maximumCapacity": iri("maximumCapacity"),
        "availabilityFraction": iri("availabilityFraction"),
        "serviceName": iri("serviceName"),
        "provider": iri("provider"),
        "capability": iri("capability"),
        "dependsOn": iri("dependsOn"),
        "criticality": iri("criticality"),
        "availabilityTarget": iri("availabilityTarget"),
        "flowType": iri("flowType"),
        "quantity": iri("quantity"),
        "strength": iri("strength"),
        "capacityFraction": iri("capacityFraction"),
        "reliability": iri("reliability"),
        "latency": iri("latency"),
        "epistemicStatus": iri("epistemicStatus"),
        "confidence": iri("confidence"),
        "evidence": iri("evidence"),
        "provenance": iri("provenance"),
        "sourceRecord": iri("sourceRecord"),
        "resolution": iri("resolution"),
        "resolutionEntity": iri("resolutionEntity"),
        "resolutionMethod": iri("resolutionMethod"),
        "resolutionDecision": iri("resolutionDecision"),
        "resolutionScore": iri("resolutionScore"),
        "resolver": iri("resolver"),
        "resolvedAt": iri("resolvedAt"),
        "rationale": iri("rationale"),
        "namespace": iri("namespace"),
        "value": iri("value"),
        "start": iri("start"),
        "end": iri("end"),
        "unit": iri("unit"),
        "latitude": iri("latitude"),
        "longitude": iri("longitude"),
        "heightM": iri("heightM"),
    }
)

ENTITY_TYPE_IRIS: Mapping[str, str] = MappingProxyType(
    {member.value: iri(f"entity-type/{member.value}") for member in EntityType}
)
RELATIONSHIP_TYPE_IRIS: Mapping[str, str] = MappingProxyType(
    {member.value: iri(f"relationship-type/{member.value}") for member in RelationshipType}
)
EVENT_TYPE_IRIS: Mapping[str, str] = MappingProxyType(
    {member.value: iri(f"event-type/{member.value}") for member in EventType}
)

_TERM_DEFINITIONS = {
    "Entity": "A persistently identifiable real-world or conceptual thing.",
    "Relationship": "A directed typed association between two entities that may carry temporal, reliability and evidence metadata.",
    "Event": "A bounded occurrence that changes or describes world state over an explicit time interval.",
    "Capability": "A realizable capacity owned by an entity, represented with a dimensioned quantity and availability envelope.",
    "Service": "A delivered function or outcome exposed to consumers and backed by providers and or capabilities.",
    "Flow": "A directed transfer of a typed quantity between entities over an explicit validity interval.",
    "Assertion": "An epistemically qualified statement about an entity or relationship, with optional evidence and provenance.",
    "EntityResolution": "An evidence-qualified mapping from an external identifier to a canonical SERAPH entity.",
    "ExternalIdentifier": "A namespace-qualified identifier value originating outside the canonical SERAPH identity system.",
    "TimeWindow": "A strict UTC-normalized half-open temporal interval [start, end).",
    "Quantity": "A dimensioned numerical value paired with an explicit unit under Core unit semantics.",
    "GeodeticPoint": "A WGS84 geodetic coordinate represented by latitude, longitude and optional height in metres.",
}


def ontology_terms() -> tuple[OntologyTerm, ...]:
    """Return the normative SERAPH ontology class surface."""
    return tuple(
        OntologyTerm(name, class_iri, "class", _TERM_DEFINITIONS[name])
        for name, class_iri in CLASS_IRIS.items()
    )


def ontology_metadata() -> dict[str, object]:
    """Return a JSON-serializable ontology manifest."""
    return {
        "ontology_profile": ONTOLOGY_PROFILE,
        "ontology_version": ONTOLOGY_VERSION,
        "world_model_schema": WORLD_MODEL_SCHEMA,
        "namespace": SERAPH_NAMESPACE,
        "context": SERAPH_CONTEXT,
        "namespaces": dict(_NAMESPACES),
        "standards_baseline": dict(STANDARDS_BASELINE),
        "classes": dict(CLASS_IRIS),
        "properties": dict(PROPERTY_IRIS),
        "entity_type_terms": dict(ENTITY_TYPE_IRIS),
        "relationship_type_terms": dict(RELATIONSHIP_TYPE_IRIS),
        "event_type_terms": dict(EVENT_TYPE_IRIS),
        "terms": [asdict(term) for term in ontology_terms()],
    }
