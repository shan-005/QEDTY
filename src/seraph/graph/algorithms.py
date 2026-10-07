"""Deterministic graph algorithms for the SERAPH reference implementation."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from collections.abc import Callable
from datetime import datetime
from heapq import heappop, heappush
from math import isfinite
from typing import TYPE_CHECKING

from seraph.ontology.relations import Relationship

from .model import FlowResult, GraphPath

if TYPE_CHECKING:
    from datetime import datetime

    from seraph.core.enums import RelationshipType

    from .store import TemporalGraph

WeightFn = Callable[[Relationship], float]


def _out_neighbors(
    graph: TemporalGraph,
    node: str,
    *,
    at: datetime | None = None,
    types: set[RelationshipType] | None = None,
) -> tuple[Relationship, ...]:
    return graph.edges_from(node, at=at, types=types)


def bfs_order(
    graph: TemporalGraph,
    source: str,
    *,
    at: datetime | None = None,
    max_hops: int | None = None,
    relationship_types: set[RelationshipType] | None = None,
) -> tuple[str, ...]:
    """Breadth-first traversal with lexicographically stable neighbor order."""

    if not graph.has_entity(source):
        raise KeyError(source)
    if max_hops is not None and max_hops < 0:
        raise ValueError("max_hops must be non-negative")
    queue: deque[tuple[str, int]] = deque([(source, 0)])
    seen = {source}
    order: list[str] = []
    while queue:
        node, depth = queue.popleft()
        if node != source:
            order.append(node)
        if max_hops is not None and depth >= max_hops:
            continue
        for edge in _out_neighbors(graph, node, at=at, types=relationship_types):
            nxt = edge.target.entity_id
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, depth + 1))
    return tuple(order)


def dfs_order(
    graph: TemporalGraph,
    source: str,
    *,
    at: datetime | None = None,
    max_hops: int | None = None,
    relationship_types: set[RelationshipType] | None = None,
) -> tuple[str, ...]:
    """Depth-first traversal with stable lexicographic expansion."""

    if not graph.has_entity(source):
        raise KeyError(source)
    if max_hops is not None and max_hops < 0:
        raise ValueError("max_hops must be non-negative")
    stack: list[tuple[str, int]] = [(source, 0)]
    seen = {source}
    order: list[str] = []
    while stack:
        node, depth = stack.pop()
        if node != source:
            order.append(node)
        if max_hops is not None and depth >= max_hops:
            continue
        neighbors = [
            edge.target.entity_id
            for edge in _out_neighbors(graph, node, at=at, types=relationship_types)
        ]
        for nxt in sorted(neighbors, reverse=True):
            if nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, depth + 1))
    return tuple(order)


def indegree_centrality(graph: TemporalGraph, *, at: datetime | None = None) -> dict[str, float]:
    n = len(graph.entities())
    denominator = max(1, n - 1)
    counts = Counter(
        edge.target.entity_id for edge in graph.relationships() if at is None or _active(edge, at)
    )
    return {entity.entity_id: counts[entity.entity_id] / denominator for entity in graph.entities()}


def outdegree_centrality(graph: TemporalGraph, *, at: datetime | None = None) -> dict[str, float]:
    n = len(graph.entities())
    denominator = max(1, n - 1)
    counts = Counter(
        edge.source.entity_id for edge in graph.relationships() if at is None or _active(edge, at)
    )
    return {entity.entity_id: counts[entity.entity_id] / denominator for entity in graph.entities()}


def pagerank(
    graph: TemporalGraph,
    *,
    at: datetime | None = None,
    damping: float = 0.85,
    tolerance: float = 1e-10,
    max_iterations: int = 200,
    weight: WeightFn | None = None,
) -> dict[str, float]:
    """Deterministic PageRank with weighted or unweighted transitions."""

    if not 0.0 < damping < 1.0:
        raise ValueError("damping must be in (0, 1)")
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")
    nodes = tuple(entity.entity_id for entity in graph.entities())
    n = len(nodes)
    if not n:
        return {}
    rank = dict.fromkeys(nodes, 1.0 / n)
    outgoing: dict[str, tuple[tuple[str, float], ...]] = {}
    for node in nodes:
        edges = graph.edges_from(node, at=at)
        if weight is None:
            weighted = [(edge.target.entity_id, 1.0) for edge in edges]
        else:
            weighted = [(edge.target.entity_id, weight(edge)) for edge in edges]
            if any(value < 0 or not isfinite(value) for _, value in weighted):
                raise ValueError("PageRank weights must be finite and non-negative")
        totals: defaultdict[str, float] = defaultdict(float)
        for target, value in weighted:
            totals[target] += value
        outgoing[node] = tuple(sorted(totals.items()))

    for _ in range(max_iterations):
        dangling_mass = sum(rank[node] for node in nodes if not outgoing[node])
        base = (1.0 - damping + damping * dangling_mass) / n
        next_rank = dict.fromkeys(nodes, base)
        for source in nodes:
            arcs = outgoing[source]
            if not arcs:
                continue
            total = sum(value for _, value in arcs)
            if total == 0.0:
                continue
            share = damping * rank[source] / total
            for target, value in arcs:
                next_rank[target] += share * value
        delta = sum(abs(next_rank[node] - rank[node]) for node in nodes)
        rank = next_rank
        if delta <= tolerance:
            break
    else:
        raise RuntimeError("PageRank failed to converge within max_iterations")
    total = sum(rank.values())
    return {node: value / total for node, value in sorted(rank.items())}


def closeness_centrality(
    graph: TemporalGraph,
    *,
    at: datetime | None = None,
    relationship_types: set[RelationshipType] | None = None,
) -> dict[str, float]:
    """Out-closeness based on hop distance in the directed graph."""

    result: dict[str, float] = {}
    nodes = tuple(entity.entity_id for entity in graph.entities())
    for source in nodes:
        distances = _hop_distances(graph, source, at=at, relationship_types=relationship_types)
        reachable = len(distances) - 1
        if reachable <= 0:
            result[source] = 0.0
            continue
        total = sum(distances.values())
        result[source] = (reachable / total) * (reachable / max(1, len(nodes) - 1))
    return result


def betweenness_centrality(graph: TemporalGraph, *, at: datetime | None = None) -> dict[str, float]:
    """Brandes-style betweenness centrality for unweighted directed graphs."""

    nodes = tuple(entity.entity_id for entity in graph.entities())
    centrality = dict.fromkeys(nodes, 0.0)
    for source in nodes:
        stack: list[str] = []
        predecessors: defaultdict[str, list[str]] = defaultdict(list)
        sigma = dict.fromkeys(nodes, 0.0)
        distance = dict.fromkeys(nodes, -1)
        sigma[source] = 1.0
        distance[source] = 0
        queue: deque[str] = deque([source])
        while queue:
            vertex = queue.popleft()
            stack.append(vertex)
            targets = sorted({edge.target.entity_id for edge in graph.edges_from(vertex, at=at)})
            for target in targets:
                if distance[target] < 0:
                    distance[target] = distance[vertex] + 1
                    queue.append(target)
                if distance[target] == distance[vertex] + 1:
                    sigma[target] += sigma[vertex]
                    predecessors[target].append(vertex)
        dependency = dict.fromkeys(nodes, 0.0)
        while stack:
            vertex = stack.pop()
            for predecessor in predecessors[vertex]:
                if sigma[vertex]:
                    dependency[predecessor] += (sigma[predecessor] / sigma[vertex]) * (
                        1.0 + dependency[vertex]
                    )
            if vertex != source:
                centrality[vertex] += dependency[vertex]
    if len(nodes) > 2:
        scale = 1.0 / ((len(nodes) - 1) * (len(nodes) - 2))
        centrality = {node: value * scale for node, value in centrality.items()}
    return centrality


def weakly_connected_components(
    graph: TemporalGraph, *, at: datetime | None = None
) -> tuple[tuple[str, ...], ...]:
    """Connected components after treating every relationship as undirected."""

    nodes = {entity.entity_id for entity in graph.entities()}
    adjacency: defaultdict[str, set[str]] = defaultdict(set)
    for edge in graph.relationships():
        if at is not None and not _active(edge, at):
            continue
        adjacency[edge.source.entity_id].add(edge.target.entity_id)
        adjacency[edge.target.entity_id].add(edge.source.entity_id)
    components: list[tuple[str, ...]] = []
    while nodes:
        root = min(nodes)
        queue = deque([root])
        nodes.remove(root)
        component = []
        while queue:
            node = queue.popleft()
            component.append(node)
            for nxt in sorted(adjacency[node]):
                if nxt in nodes:
                    nodes.remove(nxt)
                    queue.append(nxt)
        components.append(tuple(sorted(component)))
    return tuple(sorted(components))


def strongly_connected_components(
    graph: TemporalGraph, *, at: datetime | None = None
) -> tuple[tuple[str, ...], ...]:
    """Tarjan SCC decomposition with deterministic vertex ordering."""

    index = 0
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        low[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for edge in graph.edges_from(node, at=at):
            target = edge.target.entity_id
            if target not in indices:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], indices[target])
        if low[node] == indices[node]:
            component: list[str] = []
            while True:
                target = stack.pop()
                on_stack.remove(target)
                component.append(target)
                if target == node:
                    break
            components.append(tuple(sorted(component)))

    for node in sorted(entity.entity_id for entity in graph.entities()):
        if node not in indices:
            visit(node)
    return tuple(sorted(components))


def articulation_points(graph: TemporalGraph, *, at: datetime | None = None) -> tuple[str, ...]:
    """Return articulation vertices of the undirected graph projection."""

    adjacency: defaultdict[str, set[str]] = defaultdict(set)
    nodes = [entity.entity_id for entity in graph.entities()]
    for edge in graph.relationships():
        if at is not None and not _active(edge, at):
            continue
        adjacency[edge.source.entity_id].add(edge.target.entity_id)
        adjacency[edge.target.entity_id].add(edge.source.entity_id)
    discovery: dict[str, int] = {}
    low: dict[str, int] = {}
    parent: dict[str, str | None] = dict.fromkeys(nodes, None)
    cut: set[str] = set()
    clock = 0

    def dfs(node: str) -> None:
        nonlocal clock
        discovery[node] = low[node] = clock
        clock += 1
        children = 0
        for neighbor in sorted(adjacency[node]):
            if neighbor not in discovery:
                parent[neighbor] = node
                children += 1
                dfs(neighbor)
                low[node] = min(low[node], low[neighbor])
                if parent[node] is None and children > 1:
                    cut.add(node)
                if parent[node] is not None and low[neighbor] >= discovery[node]:
                    cut.add(node)
            elif neighbor != parent[node]:
                low[node] = min(low[node], discovery[neighbor])

    for node in sorted(nodes):
        if node not in discovery:
            dfs(node)
    return tuple(sorted(cut))


def topological_sort(graph: TemporalGraph, *, at: datetime | None = None) -> tuple[str, ...]:
    """Kahn topological ordering; raises when a directed cycle exists."""

    nodes = tuple(entity.entity_id for entity in graph.entities())
    indegree = dict.fromkeys(nodes, 0)
    for edge in graph.relationships():
        if at is not None and not _active(edge, at):
            continue
        indegree[edge.target.entity_id] += 1
    ready = [node for node in nodes if indegree[node] == 0]
    ready.sort()
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for edge in graph.edges_from(node, at=at):
            target = edge.target.entity_id
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()
    if len(order) != len(nodes):
        raise ValueError("graph contains a directed cycle")
    return tuple(order)


def max_flow(
    graph: TemporalGraph,
    source: str,
    target: str,
    *,
    at: datetime | None = None,
    capacity: WeightFn | None = None,
) -> FlowResult:
    """Deterministic Edmonds-Karp maximum flow over relationship capacities.

    Parallel relationships remain distinct flow channels; antiparallel
    relationships are represented with separate residual arcs.
    """

    if not graph.has_entity(source) or not graph.has_entity(target):
        raise KeyError("graph endpoint missing")
    if source == target:
        return FlowResult(source, target, 0.0, (), (source,), ())
    capacity_fn = capacity or (lambda edge: edge.capacity_fraction)
    active_edges: list[Relationship] = []
    capacities: list[float] = []
    adjacency: defaultdict[str, list[tuple[int, bool, str]]] = defaultdict(list)
    for edge in graph.relationships():
        if at is not None and not _active(edge, at):
            continue
        value = float(capacity_fn(edge))
        if value < 0.0 or not isfinite(value):
            raise ValueError("flow capacities must be finite and non-negative")
        index = len(active_edges)
        active_edges.append(edge)
        capacities.append(value)
        adjacency[edge.source.entity_id].append((index, True, edge.target.entity_id))
        adjacency[edge.target.entity_id].append((index, False, edge.source.entity_id))
    for node in adjacency:
        adjacency[node].sort(
            key=lambda arc: (arc[2], active_edges[arc[0]].relationship_id, not arc[1])
        )

    flow = [0.0 for _ in active_edges]
    epsilon = 1e-15
    total = 0.0
    while True:
        parent: dict[str, tuple[str, int, bool] | None] = {source: None}
        queue: deque[str] = deque([source])
        while queue and target not in parent:
            node = queue.popleft()
            for edge_index, forward, neighbor in adjacency[node]:
                residual = (
                    capacities[edge_index] - flow[edge_index] if forward else flow[edge_index]
                )
                if residual <= epsilon or neighbor in parent:
                    continue
                parent[neighbor] = (node, edge_index, forward)
                queue.append(neighbor)
                if neighbor == target:
                    break
        if target not in parent:
            break
        path: list[tuple[str, int, bool]] = []
        node = target
        while True:
            entry = parent[node]
            if entry is None:
                break
            previous, edge_index, forward = entry
            path.append((previous, edge_index, forward))
            node = previous
        bottleneck = min(
            capacities[edge_index] - flow[edge_index] if forward else flow[edge_index]
            for _, edge_index, forward in path
        )
        if bottleneck <= epsilon:
            break
        for _, edge_index, forward in path:
            if forward:
                flow[edge_index] += bottleneck
            else:
                flow[edge_index] -= bottleneck
        total += bottleneck

    reachable = {source}
    queue = deque([source])
    while queue:
        node = queue.popleft()
        for edge_index, forward, neighbor in adjacency[node]:
            residual = capacities[edge_index] - flow[edge_index] if forward else flow[edge_index]
            if residual > epsilon and neighbor not in reachable:
                reachable.add(neighbor)
                queue.append(neighbor)
    all_nodes = {entity.entity_id for entity in graph.entities()}
    return FlowResult(
        source=source,
        target=target,
        value=total,
        flow_by_relationship=tuple(
            sorted(
                (edge.relationship_id, value)
                for edge, value in zip(active_edges, flow, strict=True)
                if value > epsilon
            )
        ),
        source_side=tuple(sorted(reachable)),
        sink_side=tuple(sorted(all_nodes - reachable)),
    )


def shortest_path(
    graph: TemporalGraph,
    source: str,
    target: str,
    *,
    weight: WeightFn | None = None,
    at: datetime | None = None,
    relationship_types: set[RelationshipType] | None = None,
) -> GraphPath | None:
    """Dijkstra shortest path for non-negative edge costs."""

    if not graph.has_entity(source) or not graph.has_entity(target):
        raise KeyError("graph endpoint missing")
    if source == target:
        return GraphPath((source,), (), 1.0, 0.0)
    cost_fn = weight or (lambda edge: 1.0)
    heap: list[tuple[float, int, tuple[str, ...], tuple[str, ...], str]] = [
        (0.0, 0, (source,), (), source)
    ]
    best: dict[str, float] = {source: 0.0}
    while heap:
        cost, hops, nodes, relation_ids, node = heappop(heap)
        if cost > best.get(node, float("inf")) + 1e-15:
            continue
        if node == target:
            score = 1.0
            for rid in relation_ids:
                edge = graph.get_relationship(rid)
                score *= edge.strength * edge.capacity_fraction
            return GraphPath(nodes, relation_ids, score, cost)
        for edge in graph.edges_from(node, at=at, types=relationship_types):
            edge_cost = float(cost_fn(edge))
            if edge_cost < 0 or not isfinite(edge_cost):
                raise ValueError("Dijkstra weights must be finite and non-negative")
            nxt = edge.target.entity_id
            if nxt in nodes:
                continue
            new_cost = cost + edge_cost
            if new_cost + 1e-15 < best.get(nxt, float("inf")):
                best[nxt] = new_cost
                heappush(
                    heap,
                    (
                        new_cost,
                        hops + 1,
                        (*nodes, nxt),
                        (*relation_ids, edge.relationship_id),
                        nxt,
                    ),
                )
    return None


def _hop_distances(
    graph: TemporalGraph,
    source: str,
    *,
    at: datetime | None = None,
    relationship_types: set[RelationshipType] | None = None,
) -> dict[str, int]:
    queue: deque[str] = deque([source])
    distances = {source: 0}
    while queue:
        node = queue.popleft()
        for edge in graph.edges_from(node, at=at, types=relationship_types):
            nxt = edge.target.entity_id
            if nxt not in distances:
                distances[nxt] = distances[node] + 1
                queue.append(nxt)
    return distances


def _active(edge: Relationship, at: datetime) -> bool:
    from .temporal import active

    return active(edge, at)
