#!/usr/bin/env python3
"""Deterministic QEDTY Graph contract conformance check."""

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

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "tests" / "graph_golden_vectors.json"
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
    source: Entity, target: Entity, *, strength: float = 1.0, capacity: float = 1.0
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


def _graph() -> tuple[TemporalGraph, dict[str, Entity]]:
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


def run() -> int:
    # CRITICAL FIX: Use utf-8-sig to handle potential UTF-8 BOM in JSON files
    vectors = json.loads(VECTORS.read_text(encoding="utf-8-sig"))
    graph, nodes = _graph()
    labels = {entity.entity_id: name for name, entity in nodes.items()}
    checks: dict[str, bool] = {
        "schema": vectors["schema"] == KEY,
        "bfs": [labels[item] for item in bfs_order(graph, nodes["a"].entity_id)]
        == [labels[item] for item in sorted(labels) if item != nodes["a"].entity_id],
        "active": len(graph.edges_from(nodes["a"].entity_id, at=START)) == 2,
        "snapshot": len(graph.snapshot(START).entity_ids) == 3,
        "reliability": (
            [
                labels[item]
                for item in graph.shortest_paths(nodes["a"].entity_id, nodes["c"].entity_id)[
                    0
                ].entity_ids
            ]
            == ["a", "b", "c"]
            and graph.shortest_paths(nodes["a"].entity_id, nodes["c"].entity_id)[0].score == 0.81
        ),
    }
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
    flow_graph, source, target = _flow_graph()
    checks.update(
        {
            "dijkstra": weighted is not None and weighted.cost == 3.0,
            "scc": len(strongly_connected_components(graph)) == 3,
            "weak": len(weakly_connected_components(graph)) == 1,
            "pagerank": abs(sum(pagerank(graph).values()) - 1.0) < 1e-10,
            "flow": max_flow(flow_graph, source.entity_id, target.entity_id).value == 0.8,
            "persistence": loads(dumps(graph)).digest() == graph.digest(),
            "spatial": edge_length_m(
                graph, graph.edges_from(nodes["a"].entity_id)[0].relationship_id
            )
            > 1000.0,
        }
    )
    failed = []
    for name, passed in checks.items():
        print(f"Graph {name}: {'PASS' if passed else 'FAIL'}")
        if not passed:
            failed.append(name)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
