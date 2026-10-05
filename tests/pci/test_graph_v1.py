from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from decimal import Decimal

import pytest

from seraph.pci.core.enums import EntityType, EpistemicStatus, RelationshipType
from seraph.pci.core.ids import deterministic_id, sha256_hex
from seraph.pci.core.types import EntityRef, Observation, Relationship
from seraph.pci.entities.resolver import EntityResolver
from seraph.pci.evidence.models import EvidenceRecord
from seraph.pci.evidence.provenance import Provenance, ProvenanceChain
from seraph.pci.evidence.registry import EvidenceRegistry
from seraph.pci.graph.persistence import load_json, save_json
from seraph.pci.graph.builder import GraphBuilder
from seraph.pci.graph.query import GraphQuery
from seraph.pci.graph.store import TemporalGraph


UTC = timezone.utc
T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = T0 + timedelta(days=30)
T2 = T1 + timedelta(days=30)


def entity(resolver: EntityResolver, kind: EntityType, name: str) -> object:
    return resolver.make_entity(entity_type=kind, canonical_name=name)


def test_ids_are_stable() -> None:
    assert deterministic_id("entity", "a", "b") == deterministic_id("entity", "a", "b")
    assert sha256_hex({"b": 2, "a": 1}) == sha256_hex({"a": 1, "b": 2})


def test_entity_resolution_external_identity_and_alias() -> None:
    resolver = EntityResolver()
    sat = resolver.make_entity(
        entity_type=EntityType.SATELLITE,
        canonical_name="GPS IIF-1",
        aliases=["gps iif-1", "IIF-1"],
        external_ids={"catalog": "12345"},
    )
    resolver.upsert(sat)
    assert resolver.resolve_external("catalog", "12345") == sat
    assert resolver.resolve_name("IIF-1") == (sat,)


def test_relationship_identity_and_timezone() -> None:
    resolver = EntityResolver()
    a = resolver.make_entity(entity_type=EntityType.SATELLITE, canonical_name="A")
    b = resolver.make_entity(entity_type=EntityType.GNSS_SERVICE, canonical_name="B")
    edge_id = deterministic_id("rel", a.entity_id, b.entity_id, RelationshipType.PROVIDES.value, T0.isoformat(), T1.isoformat())
    edge = Relationship(
        relationship_id=edge_id,
        source=EntityRef(entity_id=a.entity_id),
        target=EntityRef(entity_id=b.entity_id),
        relationship_type=RelationshipType.PROVIDES,
        valid_from=T0,
        valid_to=T1,
        confidence=0.9,
    )
    assert edge.valid_from == T0

    with pytest.raises(ValueError):
        Observation(
            observation_id="x",
            entity_id=a.entity_id,
            observed_at=datetime(2026, 1, 1),
            property_name="availability",
            value=Decimal("1.0"),
        )


def test_temporal_queries_filter_edges() -> None:
    resolver = EntityResolver()
    s = resolver.make_entity(entity_type=EntityType.SATELLITE, canonical_name="Satellite")
    p = resolver.make_entity(entity_type=EntityType.GNSS_SERVICE, canonical_name="PNT")
    t = resolver.make_entity(entity_type=EntityType.TELECOM_NETWORK, canonical_name="Telecom")
    e1 = deterministic_id("rel", s.entity_id, p.entity_id, RelationshipType.PROVIDES.value, T0.isoformat(), T1.isoformat())
    e2 = deterministic_id("rel", p.entity_id, t.entity_id, RelationshipType.ENABLES.value, T0.isoformat(), None)
    r1 = Relationship(relationship_id=e1, source=EntityRef(entity_id=s.entity_id), target=EntityRef(entity_id=p.entity_id), relationship_type=RelationshipType.PROVIDES, valid_from=T0, valid_to=T1, confidence=0.95)
    r2 = Relationship(relationship_id=e2, source=EntityRef(entity_id=p.entity_id), target=EntityRef(entity_id=t.entity_id), relationship_type=RelationshipType.ENABLES, valid_from=T0, confidence=0.9)
    graph = TemporalGraph()
    graph.bulk_add([s, p, t], [r1, r2])
    query = GraphQuery(graph)

    assert query.dependencies(s.entity_id, at=T0 + timedelta(days=5))[0].entity_id == p.entity_id
    assert query.dependencies(s.entity_id, at=T2) == ()
    paths = query.paths(s.entity_id, t.entity_id, at=T0 + timedelta(days=5))
    assert paths and paths[0].entity_ids == (s.entity_id, p.entity_id, t.entity_id)
    assert paths[0].confidence_product == pytest.approx(0.855)


def test_graph_serialization_round_trip_is_deterministic() -> None:
    resolver = EntityResolver()
    a = resolver.make_entity(entity_type=EntityType.REGION, canonical_name="Region")
    b = resolver.make_entity(entity_type=EntityType.ECONOMIC_FUNCTION, canonical_name="Function")
    rid = deterministic_id("rel", a.entity_id, b.entity_id, RelationshipType.SUPPORTS.value, None, None)
    edge = Relationship(relationship_id=rid, source=EntityRef(entity_id=a.entity_id), target=EntityRef(entity_id=b.entity_id), relationship_type=RelationshipType.SUPPORTS, epistemic_status=EpistemicStatus.DERIVED)
    graph = TemporalGraph()
    graph.bulk_add([a, b], [edge])
    restored = TemporalGraph.from_json(graph.to_json())
    assert graph.digest() == restored.digest()
    assert restored.snapshot().entity_count == 2
    assert restored.snapshot().relationship_count == 1


def test_builder_enforces_evidence_links() -> None:
    resolver = EntityResolver()
    a = resolver.make_entity(entity_type=EntityType.SATELLITE, canonical_name="A")
    b = resolver.make_entity(entity_type=EntityType.GNSS_SERVICE, canonical_name="B")
    content = "demo source"
    evidence_id = deterministic_id("evidence", "https://example.test", "r1", sha256_hex(content), T0.isoformat())
    evidence = EvidenceRecord(
        evidence_id=evidence_id,
        source_name="Example",
        source_uri="https://example.test",
        source_record_id="r1",
        retrieved_at=T0,
        observed_at=T0,
        content_sha256=sha256_hex(content),
    )
    rid = deterministic_id("rel", a.entity_id, b.entity_id, RelationshipType.PROVIDES.value, None, None)
    rel = Relationship(
        relationship_id=rid,
        source=EntityRef(entity_id=a.entity_id),
        target=EntityRef(entity_id=b.entity_id),
        relationship_type=RelationshipType.PROVIDES,
        evidence_ids=(evidence_id,),
    )
    builder = GraphBuilder()
    builder.add_evidence(evidence)
    builder.add_entity(a)
    builder.add_entity(b)
    builder.add_relationship(rel)
    assert builder.build().get_relationship(rid) == rel


def test_provenance_parent_chain() -> None:
    parameters = {"alpha": 0.7}
    p1_id = deterministic_id("prov", "a", "agent", T0.isoformat())
    p1 = Provenance(
        provenance_id=p1_id, activity="ingest", agent="seraph", started_at=T0, software_version="0.1", parameters_digest=sha256_hex(parameters)
    )
    p2_id = deterministic_id("prov", "b", "agent", T1.isoformat())
    p2 = Provenance(
        provenance_id=p2_id, activity="derive", agent="seraph", started_at=T1, software_version="0.1", parameters_digest=sha256_hex(parameters), parent_provenance_ids=(p1_id,)
    )
    chain = ProvenanceChain()
    chain.add(p1)
    chain.add(p2)
    assert chain.ancestors(p2_id) == (p1_id,)


def test_entity_identity_uses_the_same_canonicalization_as_resolver() -> None:
    resolver = EntityResolver()
    e = resolver.make_entity(entity_type=EntityType.COMPANY, canonical_name="A&B  Holdings")
    assert e.entity_id == deterministic_id("entity", "seraph", "company", "a b holdings")


def test_evidence_registry_is_idempotent_and_strict(tmp_path: Path) -> None:
    content = "registry"
    digest = sha256_hex(content)
    eid = deterministic_id("evidence", "https://example.test", "r2", digest, T0.isoformat())
    record = EvidenceRecord(evidence_id=eid, source_name="Example", source_uri="https://example.test", source_record_id="r2", retrieved_at=T0, observed_at=T0, content_sha256=digest)
    registry = EvidenceRegistry([record])
    registry.add(record)
    assert len(registry) == 1
    assert registry.require_all([eid])[0] == record


def test_atomic_json_persistence(tmp_path: object) -> None:
    path = tmp_path / "graph.json"
    resolver = EntityResolver()
    a = resolver.make_entity(entity_type=EntityType.REGION, canonical_name="Persistence Region")
    b = resolver.make_entity(entity_type=EntityType.SERVICE, canonical_name="Persistence Service")
    rel_id = deterministic_id("rel", a.entity_id, b.entity_id, RelationshipType.SUPPORTS.value, None, None)
    rel = Relationship(relationship_id=rel_id, source=EntityRef(entity_id=a.entity_id), target=EntityRef(entity_id=b.entity_id), relationship_type=RelationshipType.SUPPORTS)
    graph = TemporalGraph(); graph.bulk_add([a, b], [rel])
    save_json(graph, path)
    restored = load_json(path)
    assert restored.digest() == graph.digest()
