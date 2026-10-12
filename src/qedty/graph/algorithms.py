"""Deterministic graph algorithms for the QEDTY reference implementation."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from collections.abc import Callable
from heapq import heappop, heappush
from math import isfinite
from typing import TYPE_CHECKING

from qedty.ontology.relations import Relationship

from .model import FlowResult, GraphPath

if TYPE_CHECKING:
    from datetime import datetime

    from qedty.core.enums import RelationshipType

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
    """Breadth-first traversal with deterministic semantic neighbor order."""

    if not graph.has_entity(source):
        raise KeyError(source)
    if max_hops is not None and max_hops < 0:
        raise ValueError("max_hops must be non-negative")

    canonical_names = {entity.entity_id: entity.canonical_name for entity in graph.entities()}

    queue: deque[tuple[str, int]] = deque([(source, 0)])
    seen = {source}
    order: list[str] = []

    while queue:
        node, depth = queue.popleft()

        if node != source:
            order.append(node)

        if max_hops is not None and depth >= max_hops:
            continue

        neighbors = sorted(
            (
                edge.target.entity_id
                for edge in _out_neighbors(
                    graph,
                    node,
                    at=at,
                    types=relationship_types,
                )
            ),
            key=lambda entity_id: (
                canonical_names[entity_id],
                entity_id,
            ),
        )

        for nxt in neighbors:
            if nxt in seen:
                continue

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
            for edge in _out_neighbors(
                graph,
                node,
                at=at,
                types=relationship_types,
            )
        ]

        for nxt in sorted(neighbors, reverse=True):
            if nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, depth + 1))

    return tuple(order)


def indegree_centrality(
    graph: TemporalGraph,
    *,
    at: datetime | None = None,
) -> dict[str, float]:
    n = len(graph.entities())
    denominator = max(1, n - 1)
    counts = Counter(
        edge.target.entity_id for edge in graph.relationships() if at is None or _active(edge, at)
    )
    return {entity.entity_id: counts[entity.entity_id] / denominator for entity in graph.entities()}


def outdegree_centrality(
    graph: TemporalGraph,
    *,
    at: datetime | None = None,
) -> dict[str, float]:
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
        scale = max((value for _, value in weighted), default=0.0)
        if scale > 0.0:
            for target, value in weighted:
                if value > 0.0:
                    totals[target] += value / scale

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
    return dict(sorted(rank.items()))


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
        distances = _hop_distances(
            graph,
            source,
            at=at,
            relationship_types=relationship_types,
        )
        reachable = len(distances) - 1

        if reachable <= 0:
            result[source] = 0.0
            continue

        total = sum(distances.values())
        result[source] = (reachable / total) * (reachable / max(1, len(nodes) - 1))

    return result


def betweenness_centrality(
    graph: TemporalGraph,
    *,
    at: datetime | None = None,
) -> dict[str, float]:
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
    graph: TemporalGraph,
    *,
    at: datetime | None = None,
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
    graph: TemporalGraph,
    *,
    at: datetime | None = None,
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


def articulation_points(
    graph: TemporalGraph,
    *,
    at: datetime | None = None,
) -> tuple[str, ...]:
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
                low[node] = min(
                    low[node],
                    discovery[neighbor],
                )

    for node in sorted(nodes):
        if node not in discovery:
            dfs(node)

    return tuple(sorted(cut))


def topological_sort(
    graph: TemporalGraph,
    *,
    at: datetime | None = None,
) -> tuple[str, ...]:
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
            key=lambda arc: (
                arc[2],
                active_edges[arc[0]].relationship_id,
                not arc[1],
            )
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

                parent[neighbor] = (
                    node,
                    edge_index,
                    forward,
                )
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
                for edge, value in zip(
                    active_edges,
                    flow,
                    strict=True,
                )
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
    """Dijkstra shortest path with deterministic discovery-order tie-breaking."""

    if not graph.has_entity(source) or not graph.has_entity(target):
        raise KeyError("graph endpoint missing")

    if source == target:
        return GraphPath((source,), (), 1.0, 0.0)

    cost_fn = weight or (lambda edge: 1.0)

    sequence = 0

    heap: list[
        tuple[
            float,
            int,
            int,
            tuple[str, ...],
            tuple[str, ...],
            str,
        ]
    ] = [
        (
            0.0,
            0,
            sequence,
            (source,),
            (),
            source,
        )
    ]

    best: dict[str, float] = {source: 0.0}

    while heap:
        cost, hops, _, nodes, relation_ids, node = heappop(heap)

        if cost > best.get(node, float("inf")) + 1e-15:
            continue

        if node == target:
            score = 1.0

            for rid in relation_ids:
                edge = graph.get_relationship(rid)
                score *= edge.strength * edge.capacity_fraction

            return GraphPath(
                nodes,
                relation_ids,
                score,
                cost,
            )

        for edge in graph.edges_from(
            node,
            at=at,
            types=relationship_types,
        ):
            edge_cost = float(cost_fn(edge))

            if edge_cost < 0 or not isfinite(edge_cost):
                raise ValueError("Dijkstra weights must be finite and non-negative")

            nxt = edge.target.entity_id

            if nxt in nodes:
                continue

            new_cost = cost + edge_cost

            if new_cost + 1e-15 < best.get(
                nxt,
                float("inf"),
            ):
                best[nxt] = new_cost
                sequence += 1

                heappush(
                    heap,
                    (
                        new_cost,
                        hops + 1,
                        sequence,
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

        for edge in graph.edges_from(
            node,
            at=at,
            types=relationship_types,
        ):
            nxt = edge.target.entity_id

            if nxt not in distances:
                distances[nxt] = distances[node] + 1
                queue.append(nxt)

    return distances


def _active(edge: Relationship, at: datetime) -> bool:
    from .temporal import active

    return active(edge, at)


def static_bfs_labels(
    nodes: list[str] | tuple[str, ...],
    edges: list[list[str]] | tuple[tuple[str, str], ...],
    source: str,
) -> tuple[str, ...]:
    """Reference for the bounded graph.static.bfs@1 contract.

    Labels are trimmed; edge endpoints implicitly create nodes; directed
    adjacency is traversed in ascending label order; duplicate edges do not
    duplicate visits; the source itself is excluded from the returned order.
    This is a static algorithmic kernel, not the temporal QEDTY world graph.
    """
    if not isinstance(nodes, (list, tuple)):
        raise ValueError("nodes must be a sequence of labels")
    if not isinstance(edges, (list, tuple)):
        raise ValueError("edges must be a sequence of directed label pairs")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source label must not be blank")

    labels: set[str] = set()

    def normalize_label(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("graph labels must be strings")
        label = value.strip()
        if not label:
            raise ValueError("graph labels must not be blank")
        return label

    for value in nodes:
        labels.add(normalize_label(value))

    normalized_edges: list[tuple[str, str]] = []
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            raise ValueError("each edge must be a two-item sequence")
        left, right = normalize_label(edge[0]), normalize_label(edge[1])
        labels.update((left, right))
        normalized_edges.append((left, right))

    start = normalize_label(source)
    if start not in labels:
        raise KeyError(start)

    adjacency: dict[str, list[str]] = defaultdict(list)
    for left, right in normalized_edges:
        adjacency[left].append(right)
    for neighbors in adjacency.values():
        neighbors.sort()

    queue: deque[str] = deque([start])
    seen = {start}
    order: list[str] = []
    while queue:
        current = queue.popleft()
        for target in adjacency.get(current, ()):
            if target not in seen:
                seen.add(target)
                order.append(target)
                queue.append(target)
    return tuple(order)


def static_scc_labels(
    nodes: list[str] | tuple[str, ...],
    edges: list[list[str]] | tuple[tuple[str, str], ...],
) -> tuple[tuple[str, ...], ...]:
    """Reference for the bounded graph.static.scc contract.

    Labels are trimmed and must be non-blank strings. Directed edge endpoints
    implicitly create vertices and repeated edges are idempotent. Every SCC is
    sorted, then the complete list of components is sorted lexically. This is a
    static kernel, not the temporal QEDTY world graph.
    """
    if not isinstance(nodes, (list, tuple)):
        raise ValueError("nodes must be a sequence of labels")
    if not isinstance(edges, (list, tuple)):
        raise ValueError("edges must be a sequence of directed label pairs")

    labels: set[str] = set()

    def normalize_label(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("graph labels must be strings")
        label = value.strip()
        if not label:
            raise ValueError("graph labels must not be blank")
        return label

    for value in nodes:
        labels.add(normalize_label(value))

    normalized_edges: list[tuple[str, str]] = []
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            raise ValueError("each edge must be a two-item sequence")
        left, right = normalize_label(edge[0]), normalize_label(edge[1])
        labels.update((left, right))
        normalized_edges.append((left, right))

    adjacency: dict[str, set[str]] = {label: set() for label in labels}
    reverse: dict[str, set[str]] = {label: set() for label in labels}
    for left, right in normalized_edges:
        adjacency[left].add(right)
        reverse[right].add(left)

    ordered_adjacency = {label: tuple(sorted(neighbors)) for label, neighbors in adjacency.items()}
    ordered_reverse = {label: tuple(sorted(neighbors)) for label, neighbors in reverse.items()}

    # Iterative Kosaraju first pass avoids Python recursion limits.
    visited: set[str] = set()
    finishing_order: list[str] = []
    for start in sorted(labels):
        if start in visited:
            continue
        visited.add(start)
        stack: list[tuple[str, int]] = [(start, 0)]
        while stack:
            node, next_index = stack[-1]
            neighbors = ordered_adjacency[node]
            if next_index < len(neighbors):
                target = neighbors[next_index]
                stack[-1] = (node, next_index + 1)
                if target not in visited:
                    visited.add(target)
                    stack.append((target, 0))
            else:
                finishing_order.append(node)
                stack.pop()

    # Second pass on the reversed graph; canonicalize both output levels.
    visited.clear()
    components: list[tuple[str, ...]] = []
    for start in reversed(finishing_order):
        if start in visited:
            continue
        visited.add(start)
        component_stack: list[str] = [start]
        component: list[str] = []
        while component_stack:
            node = component_stack.pop()
            component.append(node)
            for target in reversed(ordered_reverse[node]):
                if target not in visited:
                    visited.add(target)
                    component_stack.append(target)
        components.append(tuple(sorted(component)))

    return tuple(sorted(components))


def static_shortest_path_labels(
    nodes: list[str] | tuple[str, ...],
    edges: list[list[object]] | tuple[tuple[object, ...], ...],
    source: str,
    target: str,
) -> dict[str, object] | None:
    """Reference for the bounded graph.static.shortest_path@1 contract.

    Edges are directed triples [from, to, non-negative-cost]. Node labels and
    endpoints are trimmed; edge endpoints implicitly add nodes. Dijkstra ties
    are resolved by ascending current label, then the lexically smaller parent.
    Returns the inclusive node path and additive cost, or None when unreachable.
    """
    if not isinstance(nodes, (list, tuple)):
        raise ValueError("nodes must be a sequence of labels")
    if not isinstance(edges, (list, tuple)):
        raise ValueError("edges must be a sequence of weighted directed triples")

    def normalize_label(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("graph labels must be strings")
        label = value.strip()
        if not label:
            raise ValueError("graph labels must not be blank")
        return label

    labels: set[str] = set()
    for value in nodes:
        labels.add(normalize_label(value))

    normalized_edges: list[tuple[str, str, float]] = []
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 3:
            raise ValueError("each weighted edge must be a three-item sequence")
        left, right = normalize_label(edge[0]), normalize_label(edge[1])
        raw_cost = edge[2]
        if isinstance(raw_cost, bool) or not isinstance(raw_cost, (int, float)):
            raise ValueError("edge cost must be a number")
        cost = float(raw_cost)
        if not isfinite(cost) or cost < 0.0:
            raise ValueError("edge cost must be finite and non-negative")
        labels.update((left, right))
        normalized_edges.append((left, right, cost))

    start, goal = normalize_label(source), normalize_label(target)
    if start not in labels:
        raise KeyError(start)
    if goal not in labels:
        raise KeyError(goal)

    adjacency: dict[str, list[tuple[str, float]]] = {label: [] for label in labels}
    for left, right, cost in normalized_edges:
        adjacency[left].append((right, cost))
    for outgoing in adjacency.values():
        outgoing.sort(key=lambda item: (item[0], item[1]))

    distance = dict.fromkeys(labels, float("inf"))
    previous: dict[str, str] = {}
    remaining = set(labels)
    distance[start] = 0.0

    while remaining:
        finite = ((distance[node], node) for node in remaining if isfinite(distance[node]))
        current_item = min(finite, default=None)
        if current_item is None:
            break
        current_distance, current = current_item
        remaining.remove(current)
        if current == goal:
            break
        for neighbor, edge_cost in adjacency[current]:
            if neighbor not in remaining:
                continue
            candidate = current_distance + edge_cost
            if not isfinite(candidate):
                continue
            old = distance[neighbor]
            old_parent = previous.get(neighbor)
            if candidate < old or (
                candidate == old and (old_parent is None or current < old_parent)
            ):
                distance[neighbor] = candidate
                previous[neighbor] = current

    score = distance[goal]
    if not isfinite(score):
        return None

    path = [goal]
    current = goal
    while current != start:
        parent = previous.get(current)
        if parent is None:
            raise ValueError("shortest path predecessor chain is incomplete")
        path.append(parent)
        current = parent
    path.reverse()
    return {"nodes": path, "cost": score}


def static_wcc_labels(
    nodes: list[str] | tuple[str, ...],
    edges: list[list[str]] | tuple[tuple[str, str], ...],
) -> tuple[tuple[str, ...], ...]:
    """Reference for the bounded graph.static.wcc@1 contract.

    Treat directed edges as undirected for connectivity. Labels are trimmed;
    edge endpoints implicitly create nodes; repeated edges are idempotent.
    Each component and the complete component list are sorted lexically.
    """
    if not isinstance(nodes, (list, tuple)):
        raise ValueError("nodes must be a sequence of labels")
    if not isinstance(edges, (list, tuple)):
        raise ValueError("edges must be a sequence of undirected label pairs")

    def normalize_label(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("graph labels must be strings")
        label = value.strip()
        if not label:
            raise ValueError("graph labels must not be blank")
        return label

    labels: set[str] = set()
    for value in nodes:
        labels.add(normalize_label(value))

    normalized_edges: list[tuple[str, str]] = []
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            raise ValueError("each edge must be a two-item sequence")
        left, right = normalize_label(edge[0]), normalize_label(edge[1])
        labels.update((left, right))
        normalized_edges.append((left, right))

    adjacency: dict[str, set[str]] = {label: set() for label in labels}
    for left, right in normalized_edges:
        adjacency[left].add(right)
        adjacency[right].add(left)

    unseen = set(labels)
    components: list[tuple[str, ...]] = []
    while unseen:
        root = min(unseen)
        unseen.remove(root)
        queue = [root]
        cursor = 0
        component: list[str] = []
        while cursor < len(queue):
            current = queue[cursor]
            cursor += 1
            component.append(current)
            for neighbor in sorted(adjacency[current]):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
        components.append(tuple(sorted(component)))

    return tuple(sorted(components))


def static_pagerank_labels(
    nodes: list[str] | tuple[str, ...],
    edges: list[list[object]] | tuple[tuple[object, ...], ...],
    *,
    iterations: int,
    damping: float,
) -> tuple[float, ...]:
    """Reference for the bounded graph.static.pagerank@1 contract.

    This is unweighted, label-only directed PageRank with exactly the requested
    number of sweeps. Edge endpoints implicitly add labels, parallel edges count
    separately, dangling mass is redistributed uniformly, and output is sorted.
    """
    if not isinstance(nodes, (list, tuple)):
        raise ValueError("nodes must be a sequence of labels")
    if not isinstance(edges, (list, tuple)):
        raise ValueError("edges must be a sequence of directed label pairs")
    if (
        isinstance(iterations, bool)
        or not isinstance(iterations, int)
        or not 1 <= iterations <= 1000
    ):
        raise ValueError("iterations must be an integer in [1, 1000]")
    if isinstance(damping, bool) or not isinstance(damping, (int, float)):
        raise ValueError("damping must be numeric")
    damping_value = float(damping)
    if not isfinite(damping_value) or not 0.0 < damping_value < 1.0:
        raise ValueError("damping must be finite and in (0, 1)")

    def normalize_label(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("graph labels must be strings")
        label = value.strip()
        if not label:
            raise ValueError("graph labels must not be blank")
        return label

    labels: set[str] = set()
    for value in nodes:
        labels.add(normalize_label(value))

    normalized_edges: list[tuple[str, str]] = []
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            raise ValueError("each edge must be a two-item sequence")
        left, right = normalize_label(edge[0]), normalize_label(edge[1])
        labels.update((left, right))
        normalized_edges.append((left, right))

    if not labels:
        raise ValueError("PageRank graph must contain at least one node")

    ordered_labels = tuple(sorted(labels))
    normalized_edges.sort()
    outgoing_counts = Counter(left for left, _ in normalized_edges)
    node_count = float(len(ordered_labels))
    scores = dict.fromkeys(ordered_labels, 1.0 / node_count)

    for _ in range(iterations):
        dangling_mass = sum(
            scores[label] for label in ordered_labels if outgoing_counts[label] == 0
        )
        base = (1.0 - damping_value) / node_count + damping_value * dangling_mass / node_count
        next_scores = dict.fromkeys(ordered_labels, base)
        for source, target in normalized_edges:
            count = outgoing_counts[source]
            if count > 0:
                next_scores[target] += damping_value * scores[source] / count
        scores = next_scores

    total = sum(scores[label] for label in ordered_labels)
    if not isfinite(total) or total <= 0.0:
        raise ValueError("PageRank scores must have a finite positive total")
    return tuple(scores[label] / total for label in ordered_labels)
