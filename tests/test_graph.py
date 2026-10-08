from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from qedty.core.enums import EntityType, RelationshipType
from qedty.core.hash import deterministic_id
from qedty.core.types import TimeWindow
from qedty.graph.algorithms import (
    articulation_points,
    betweenness_centrality,
    bfs_order,
    closeness_centrality,
    dfs_order,
    indegree_centrality,
    max_flow,
    outdegree_centrality,
    pagerank,
    shortest_path,
    strongly_connected_components,
    topological_sort,
    weakly_connected_components,
)
from qedty.graph.builder import from_items, from_world, induced_subgraph, merge
from qedty.graph.model import GraphPath
from qedty.graph.persistence import dumps, load, loads, save
from qedty.graph.query import (
    entities_on_paths,
    filter_entities,
    filter_relationships,
    neighborhood,
    reachable,
    relationship_cut,
)
from qedty.graph.spatial import edge_length_m, entities_within_radius
from qedty.graph.store import TemporalGraph
from qedty.graph.temporal import active, active_for_entire_window, overlaps_window
from qedty.ontology.entities import Entity
from qedty.ontology.relations import Relationship
from qedty.spatial.models import Point

if TYPE_CHECKING:
    from pathlib import Path

START = datetime(2026, 1, 1, tzinfo=UTC)
END = START + timedelta(days=1)
MID = START + timedelta(hours=12)


def entity(
    name: str,
    entity_type: EntityType = EntityType.OTHER,
    *,
    lat: float | None = None,
    lon: float | None = None,
) -> Entity:
    return Entity(
        entity_id=deterministic_id("entity", "qedty", entity_type.value, name),
        entity_type=entity_type,
        canonical_name=name,
        latitude=lat,
        longitude=lon,
    )


def relationship(
    source: Entity,
    target: Entity,
    relationship_type: RelationshipType = RelationshipType.CONNECTS_TO,
    *,
    strength: float = 1.0,
    capacity: float = 1.0,
    start: datetime | None = START,
    end: datetime | None = END,
) -> Relationship:
    valid_time = None
    if start is not None and end is not None:
        valid_time = TimeWindow(start=start, end=end)
    return Relationship(
        relationship_id=deterministic_id(
            "rel",
            source.entity_id,
            target.entity_id,
            relationship_type.value,
            start.isoformat() if start else None,
            end.isoformat() if end else None,
        ),
        source={"entity_id": source.entity_id},
        target={"entity_id": target.entity_id},
        relationship_type=relationship_type,
        valid_time=valid_time,
        strength=strength,
        capacity_fraction=capacity,
    )


def base_graph() -> tuple[TemporalGraph, Entity, Entity, Entity, Entity]:
    a, b, c, d = entity("a"), entity("b"), entity("c"), entity("d")
    graph = TemporalGraph()
    graph.add_many(
        [
            a,
            b,
            c,
            d,
            relationship(a, b),
            relationship(b, c),
            relationship(a, d, strength=0.8),
            relationship(d, c, strength=0.8),
        ]
    )
    return graph, a, b, c, d


def test_legacy_temporal_path_contract() -> None:
    graph, a, b, _, _ = base_graph()
    paths = graph.shortest_paths(a.entity_id, b.entity_id, at=START)
    assert paths[0].hops == 1


def test_collision_and_remove_semantics() -> None:
    graph, a, b, _, _ = base_graph()
    with pytest.raises(ValueError):
        graph.add_entity(a.model_copy(update={"canonical_name": "different"}))
    edge = relationship(a, b)
    assert graph.remove_relationship(edge.relationship_id) is not None
    graph.add_relationship(edge)
    with pytest.raises(ValueError):
        graph.remove_entity(a.entity_id)
    assert graph.remove_entity(a.entity_id, cascade=True) is not None
    assert not graph.has_entity(a.entity_id)


def test_temporal_filters_and_snapshot() -> None:
    graph, a, _, _, _ = base_graph()
    assert graph.edges_from(a.entity_id, at=START)
    assert not graph.edges_from(a.entity_id, at=END)
    snapshot = graph.snapshot(MID)
    assert len(snapshot.entity_ids) == 4
    assert len(snapshot.relationship_ids) == 4
    edge = graph.edges_from(a.entity_id)[0]
    assert active(edge, MID)
    assert not active(edge, END)
    assert overlaps_window(edge, START, END)
    assert active_for_entire_window(edge, START, END)


def test_traversals_and_reachability() -> None:
    graph, a, b, c, d = base_graph()
    assert bfs_order(graph, a.entity_id) == (b.entity_id, d.entity_id, c.entity_id)
    assert set(dfs_order(graph, a.entity_id)) == {b.entity_id, c.entity_id, d.entity_id}
    assert set(reachable(graph, a.entity_id, max_hops=2)) == {b.entity_id, c.entity_id, d.entity_id}
    assert set(neighborhood(graph, c.entity_id, hops=1)) == {b.entity_id, d.entity_id}


def test_reliability_paths_are_ordered() -> None:
    graph, a, _, c, _ = base_graph()
    paths = graph.shortest_paths(a.entity_id, c.entity_id, max_results=2)
    assert len(paths) == 2
    assert paths[0].score > paths[1].score
    assert paths[0].geometric_mean_edge_score == pytest.approx(1.0)


def test_dijkstra_and_query_shortest_path() -> None:
    graph, a, b, c, d = base_graph()
    path = shortest_path(
        graph,
        a.entity_id,
        c.entity_id,
        weight=lambda edge: 2.0 if edge.target.entity_id == c.entity_id else 1.0,
    )
    assert path is not None
    assert path.entity_ids == (a.entity_id, b.entity_id, c.entity_id)
    assert path.cost == pytest.approx(3.0)
    assert entities_on_paths([path]) == tuple(sorted(path.entity_ids))
    assert d.entity_id not in path.entity_ids


def test_components_cycles_and_topological_order() -> None:
    graph, a, _, c, _ = base_graph()
    assert len(weakly_connected_components(graph)) == 1
    assert len(strongly_connected_components(graph)) == 4
    assert topological_sort(graph)
    graph.add_relationship(relationship(c, a))
    with pytest.raises(ValueError):
        topological_sort(graph)


def test_strong_component_cycle() -> None:
    graph = TemporalGraph()
    a, b, c = entity("a"), entity("b"), entity("c")
    graph.add_many([a, b, c, relationship(a, b), relationship(b, a), relationship(b, c)])
    components = strongly_connected_components(graph)
    assert tuple(sorted((a.entity_id, b.entity_id))) in components
    assert (c.entity_id,) in components


def test_articulation_points() -> None:
    graph = TemporalGraph()
    a, b, c = entity("a"), entity("b"), entity("c")
    graph.add_many([a, b, c, relationship(a, b), relationship(b, c)])
    assert articulation_points(graph) == (b.entity_id,)


def test_centrality_algorithms() -> None:
    graph, _, _, _, _ = base_graph()
    page_rank = pagerank(graph)
    assert abs(sum(page_rank.values()) - 1.0) < 1e-9
    assert set(indegree_centrality(graph)) == {e.entity_id for e in graph.entities()}
    assert set(outdegree_centrality(graph)) == {e.entity_id for e in graph.entities()}
    assert set(closeness_centrality(graph)) == set(page_rank)
    assert set(betweenness_centrality(graph)) == set(page_rank)


def test_page_rank_weight_validation() -> None:
    graph, a, b, _, _ = base_graph()
    with pytest.raises(ValueError):
        pagerank(graph, weight=lambda _edge: -1.0)
    assert a.entity_id in pagerank(graph)
    assert b.entity_id in pagerank(graph)


def test_max_flow_parallel_and_antiparallel() -> None:
    graph = TemporalGraph()
    s, a, t = entity("s"), entity("a"), entity("t")
    graph.add_many(
        [
            s,
            a,
            t,
            relationship(s, a, capacity=0.4),
            relationship(s, a, capacity=0.3, relationship_type=RelationshipType.PROVIDES),
            relationship(a, t, capacity=0.7),
            relationship(s, t, capacity=0.2),
            relationship(t, s, capacity=0.9, relationship_type=RelationshipType.SUPPORTS),
        ]
    )
    result = max_flow(graph, s.entity_id, t.entity_id)
    assert result.value == pytest.approx(0.9)
    source_flow = sum(
        value
        for rid, value in result.flow_by_relationship
        if graph.get_relationship(rid).source.entity_id == s.entity_id
    )
    assert source_flow == pytest.approx(result.value)
    assert t.entity_id not in result.source_side


def test_filters_and_induced_subgraph() -> None:
    graph, a, b, _, _ = base_graph()
    selected = filter_entities(graph, entity_ids=[a.entity_id, b.entity_id])
    assert tuple(entity.entity_id for entity in selected) == (a.entity_id, b.entity_id)
    rels = filter_relationships(graph, relationship_types={RelationshipType.CONNECTS_TO}, at=MID)
    assert len(rels) == 4
    subgraph = induced_subgraph(graph, [a.entity_id, b.entity_id])
    assert len(subgraph.entities()) == 2
    assert len(subgraph.relationships()) == 1
    with pytest.raises(KeyError):
        induced_subgraph(graph, ["missing"])


def test_relationship_cut() -> None:
    graph, a, b, c, d = base_graph()
    assert (
        relationship_cut(graph, a.entity_id, c.entity_id, [relationship(a, b).relationship_id])
        is False
    )
    assert (
        relationship_cut(
            graph,
            a.entity_id,
            c.entity_id,
            [relationship(a, b).relationship_id, relationship(a, d, strength=0.8).relationship_id],
        )
        is True
    )
    assert d.entity_id in reachable(graph, a.entity_id)


def test_persistence_roundtrip_and_tamper_detection(tmp_path: Path) -> None:
    graph, _, _, _, _ = base_graph()
    data = dumps(graph)
    restored = loads(data)
    assert restored.digest() == graph.digest()
    path = tmp_path / "graph.json.gz"
    save(graph, path)
    assert load(path).digest() == graph.digest()
    raw = json.loads(data)
    raw["digest"] = "0" * 64
    with pytest.raises(ValueError):
        loads(json.dumps(raw))


def test_digest_is_order_invariant() -> None:
    graph_a, *_ = base_graph()
    graph_b = TemporalGraph()
    for entity in reversed(graph_a.entities()):
        graph_b.add_entity(entity)
    for rel in reversed(graph_a.relationships()):
        graph_b.add_relationship(rel)
    assert graph_a.digest() == graph_b.digest()


def test_builders_and_merge() -> None:
    graph, _, _, _, _ = base_graph()
    items = [*graph.entities(), *graph.relationships()]
    assert from_items(reversed(items)).digest() == graph.digest()
    assert merge(graph, graph).digest() == graph.digest()
    with pytest.raises(TypeError):
        from_items([object()])
    world = type(
        "World",
        (),
        {
            "entities": {e.entity_id: e for e in graph.entities()},
            "relationships": {r.relationship_id: r for r in graph.relationships()},
        },
    )()
    assert from_world(world).digest() == graph.digest()


def test_graph_stats() -> None:
    graph, _, _, _, _ = base_graph()
    stats = graph.stats()
    assert stats.entities == 4
    assert stats.relationships == 4
    assert stats.max_out_degree == 2
    assert stats.max_in_degree == 2
    assert stats.isolated_entities == 0


def test_spatial_helpers() -> None:
    graph = TemporalGraph()
    a = entity("a", lat=0.0, lon=0.0)
    b = entity("b", lat=0.0, lon=0.01)
    rel = relationship(a, b)
    graph.add_many([a, b, rel])
    assert edge_length_m(graph, rel.relationship_id) > 1000.0
    nearby = entities_within_radius(graph, Point(latitude=0.0, longitude=0.0), 2000.0)
    assert nearby[0][0] == a.entity_id
    assert nearby[1][0] == b.entity_id


def test_graph_path_validation() -> None:
    with pytest.raises(ValueError):
        GraphPath(("a",), ("r",), 1.0)
    with pytest.raises(ValueError):
        GraphPath(("a", "b"), ("r",), -1.0)
    path = GraphPath(("a", "b"), ("r",), 0.5)
    assert path.source == "a"
    assert path.target == "b"


def test_arrow_optional_fails_cleanly_without_pyarrow() -> None:
    import importlib.util

    import pytest

    # If pyarrow is installed, we cannot easily test the missing behavior
    # without breaking the environment, so we skip the test.
    if importlib.util.find_spec("pyarrow") is not None:
        pytest.skip("pyarrow is installed, skipping missing-pyarrow test")

    import importlib

    import qedty.graph.arrow as arrow_mod

    importlib.reload(arrow_mod)
    with pytest.raises(RuntimeError, match="pyarrow"):
        arrow_mod.to_arrow_tables(base_graph()[0])
