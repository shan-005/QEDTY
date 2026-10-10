from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from qedty.core.enums import EntityType, RelationshipType
from qedty.core.hash import deterministic_id
from qedty.core.types import TimeWindow
from qedty.graph.algorithms import (
    bfs_order,
    max_flow,
    pagerank,
    shortest_path,
    strongly_connected_components,
    weakly_connected_components,
)
from qedty.graph.persistence import dumps, loads
from qedty.graph.schema import KEY
from qedty.graph.spatial import edge_length_m
from qedty.graph.store import TemporalGraph
from qedty.ontology.entities import Entity
from qedty.ontology.relations import Relationship

START = datetime(2026, 1, 1, tzinfo=UTC)
END = START + timedelta(days=1)


def _entity(name: str, *, lat: float | None = None, lon: float | None = None) -> Entity:
    return Entity(
        entity_id=deterministic_id("entity", "qedty", EntityType.OTHER.value, name),
        entity_type=EntityType.OTHER,
        canonical_name=name,
        latitude=lat,
        longitude=lon,
    )


def _relationship(
    source: Entity,
    target: Entity,
    *,
    strength: float = 1.0,
    capacity: float = 1.0,
) -> Relationship:
    return Relationship(
        relationship_id=deterministic_id(
            "rel",
            source.entity_id,
            target.entity_id,
            RelationshipType.CONNECTS_TO.value,
            START.isoformat(),
            END.isoformat(),
        ),
        source={"entity_id": source.entity_id},
        target={"entity_id": target.entity_id},
        relationship_type=RelationshipType.CONNECTS_TO,
        valid_time=TimeWindow(start=START, end=END),
        strength=strength,
        capacity_fraction=capacity,
    )


def _chain() -> tuple[TemporalGraph, dict[str, Entity]]:
    nodes = {
        name: _entity(name, lat=float(index), lon=0.0) for index, name in enumerate(("a", "b", "c"))
    }
    graph = TemporalGraph()
    graph.add_many(nodes.values())
    graph.add_many(
        [
            _relationship(nodes["a"], nodes["b"], strength=0.9),
            _relationship(nodes["b"], nodes["c"], strength=0.9),
            _relationship(nodes["a"], nodes["c"], strength=0.5),
        ]
    )
    return graph, nodes


def _flow_graph() -> tuple[TemporalGraph, Entity, Entity]:
    source, via, target = _entity("flow-source"), _entity("flow-via"), _entity("flow-target")
    graph = TemporalGraph()
    graph.add_many(
        [
            source,
            via,
            target,
            _relationship(source, via, capacity=0.5),
            _relationship(via, target, capacity=0.5),
            _relationship(source, target, capacity=0.3),
        ]
    )
    return graph, source, target


def test_graph_golden_vectors() -> None:
    vectors = json.loads(Path("tests/graph_golden_vectors.json").read_text(encoding="utf-8-sig"))
    graph, nodes = _chain()
    labels = {entity.entity_id: name for name, entity in nodes.items()}
    assert vectors["schema"] == KEY
    # BFS is deterministic in graph edge insertion order.
    # _chain() inserts a->b before a->c, so b is visited before c.
    assert [labels[item] for item in bfs_order(graph, nodes["a"].entity_id)] == [
        "b",
        "c",
    ]
    assert len(graph.edges_from(nodes["a"].entity_id, at=START)) == 2
    assert len(graph.snapshot(START).entity_ids) == 3
    best = graph.shortest_paths(nodes["a"].entity_id, nodes["c"].entity_id)[0]
    assert [labels[item] for item in best.entity_ids] == ["a", "b", "c"]
    assert best.score == 0.81
    weighted = shortest_path(
        graph,
        nodes["a"].entity_id,
        nodes["c"].entity_id,
        weight=lambda edge: (
            5.0
            if (
                edge.source.entity_id == nodes["a"].entity_id
                and edge.target.entity_id == nodes["c"].entity_id
            )
            else (2.0 if edge.target.entity_id == nodes["c"].entity_id else 1.0)
        ),
    )
    assert weighted is not None
    assert weighted.cost == 3.0
    assert len(strongly_connected_components(graph)) == 3
    assert len(weakly_connected_components(graph)) == 1
    assert abs(sum(pagerank(graph).values()) - 1.0) < 1e-10
    flow_graph, source, target = _flow_graph()
    assert max_flow(flow_graph, source.entity_id, target.entity_id).value == 0.8
    assert loads(dumps(graph)).digest() == graph.digest()
    assert edge_length_m(graph, graph.edges_from(nodes["a"].entity_id)[0].relationship_id) > 1000.0


def test_python_algorithms_match_shared_graph_vectors() -> None:
    document = json.loads(Path("tests/graph_golden_vectors.json").read_text(encoding="utf-8-sig"))
    vectors = {item["name"]: item for item in document["vectors"]}

    graph, nodes = _chain()
    labels = {entity.entity_id: name for name, entity in nodes.items()}

    temporal = vectors["temporal_chain"]
    actual_bfs = [labels[item] for item in bfs_order(graph, nodes["a"].entity_id)]
    assert actual_bfs == temporal["bfs_labels"]
    assert (
        len(graph.edges_from(nodes["a"].entity_id, at=START)) == (temporal["active_relationships"])
    )
    assert len(graph.snapshot(START).entity_ids) == temporal["snapshot_entities"]

    reliability = vectors["reliability_preference"]
    best = graph.shortest_paths(nodes["a"].entity_id, nodes["c"].entity_id)[0]
    assert [labels[item] for item in best.entity_ids] == (reliability["best_path_labels"])
    assert abs(best.score - reliability["best_path_score"]) < 1e-12

    weighted = vectors["weighted_shortest_path"]
    result = shortest_path(
        graph,
        nodes["a"].entity_id,
        nodes["c"].entity_id,
        weight=lambda edge: (
            5.0
            if (
                edge.source.entity_id == nodes["a"].entity_id
                and edge.target.entity_id == nodes["c"].entity_id
            )
            else (2.0 if edge.target.entity_id == nodes["c"].entity_id else 1.0)
        ),
    )
    assert result is not None
    assert [labels[item] for item in result.entity_ids] == (weighted["shortest_path_labels"])
    assert abs(result.cost - weighted["shortest_path_cost"]) < 1e-12

    connectivity = vectors["connectivity"]
    assert len(strongly_connected_components(graph)) == (connectivity["strong_component_count"])
    assert len(weakly_connected_components(graph)) == (connectivity["weak_component_count"])

    rank_sum = sum(pagerank(graph).values())
    assert abs(rank_sum - vectors["centrality"]["pagerank_sum"]) < 1e-10

    flow_graph, source, target = _flow_graph()
    flow_value = max_flow(flow_graph, source.entity_id, target.entity_id).value
    assert abs(flow_value - vectors["max_flow"]["max_flow"]) < 1e-12

    assert vectors["persistence"]["digest_stable"] is True
    assert loads(dumps(graph)).digest() == graph.digest()

    edge = graph.edges_from(nodes["a"].entity_id)[0]
    minimum_distance = vectors["spatial_delegate"]["minimum_distance_m"]
    assert edge_length_m(graph, edge.relationship_id) > minimum_distance
