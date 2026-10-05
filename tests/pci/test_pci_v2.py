from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from seraph.pci.core.enums import EntityType
from seraph.pci.core.ids import deterministic_id
from seraph.pci.core.types import EntityRef, Relationship
from seraph.pci.entities.resolver import EntityResolver
from seraph.pci.graph.persistence import load_json, save_json
from seraph.pci.graph.query import GraphQuery
from seraph.pci.sources.space.gnss_demo import build_demo_graph, run_demo
from seraph.pci.shocks import Shock, ShockPropagator
from seraph.pci.core.enums import ShockType


def test_gnss_to_economic_path() -> None:
    graph = build_demo_graph()
    entities = {x.canonical_name: x for x in graph.entities()}
    paths = GraphQuery(graph).paths(entities["GNSS GPS Constellation"].entity_id, entities["Digital Payments"].entity_id, at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    assert paths
    assert paths[0].hops == 4
    assert paths[0].confidence_product > 0


def test_json_round_trip_is_deterministic(tmp_path) -> None:
    graph = build_demo_graph()
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    save_json(graph, first)
    restored = load_json(first)
    save_json(restored, second)
    assert first.read_bytes() == second.read_bytes()


def test_temporal_expiration() -> None:
    graph = build_demo_graph()
    entities = {x.canonical_name: x for x in graph.entities()}
    paths = GraphQuery(graph).paths(entities["GNSS GPS Constellation"].entity_id, entities["Digital Payments"].entity_id, at=datetime(2027, 2, 1, tzinfo=timezone.utc))
    assert paths == ()


def test_resolver_external_identity() -> None:
    resolver = EntityResolver()
    entity = resolver.make_entity(entity_type=EntityType.SATELLITE, canonical_name="Example Sat", external_ids={"catalog": "123"})
    resolver.upsert(entity)
    assert resolver.resolve_external("catalog", "123") == entity


def test_shock_propagation_is_deterministic() -> None:
    graph = build_demo_graph()
    source = next(e for e in graph.entities() if e.canonical_name == "GNSS GPS Constellation")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc); end = start + timedelta(hours=24)
    shock = Shock(
        shock_id=deterministic_id("shock", "x", ShockType.GNSS_INTERFERENCE.value, source.entity_id, start.isoformat(), end.isoformat(), 0.6),
        name="x", shock_type=ShockType.GNSS_INTERFERENCE, source_entity_id=source.entity_id, start=start, end=end, severity=0.6,
    )
    first = ShockPropagator(graph).propagate(shock)
    second = ShockPropagator(graph).propagate(shock)
    assert first == second


def test_demo_end_to_end() -> None:
    result = run_demo()
    assert result["nodes"] == 5
    assert result["relationships"] == 4
    assert result["path_hops"] == 4
    assert 0 < result["minimum_capacity_fraction"] < 1
    assert result["modeled_loss_usd"] > 0
    assert result["counterfactual_continuity_gain"] > 0
