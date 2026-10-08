# QEDTY Graph research baseline — 2026-10-06

This baseline was researched against current public standards, graph systems, benchmark programs, and foundational graph-algorithm literature. It defines engineering choices for the Python reference implementation; it is not a claim that QEDTY matches any commercial database or benchmark result.

## Standards and graph data models

- ISO/IEC 39075:2024 (GQL) defines property-graph data structures and a language for creating, accessing, querying, maintaining and controlling property graphs.
- SQL:2023 Part 16 (SQL/PGQ) adds property-graph queries to the SQL standard, including graph pattern matching over relational data.
- RDF remains important at the semantic/provenance boundary; the QEDTY Graph core therefore stays a native property-graph representation while supporting interoperability rather than making RDF its in-memory execution model.

## Algorithms and theory

- BFS/DFS are fundamental traversal primitives. Temporal graph research shows that adding time changes their semantics, so QEDTY separates static traversal from valid-time snapshot traversal and keeps time filtering explicit.
- Dijkstra remains the reference for non-negative cost shortest paths. Reliability paths are kept as a distinct multiplicative score objective rather than pretending reliability is an additive distance.
- Tarjan-style DFS is used for strongly connected components and articulation-point analysis.
- Brandes-style dependency accumulation is used for unweighted betweenness centrality.
- PageRank is implemented as a deterministic power-iteration method with explicit damping, tolerance and iteration limits.
- Edmonds-Karp is used for the small/reference max-flow implementation; later native implementations may use push-relabel or parallel flow algorithms when benchmarks demonstrate a need.

## Temporal graphs

Temporal-graph research emphasizes that reachability and traversal become materially different when edges have activation times. QEDTY therefore treats the Temporal layer as authoritative and Graph as its consumer rather than duplicating interval semantics.

The Aion temporal graph database research is particularly relevant to the future storage architecture: its hybrid approach separates point/update-oriented lineage access from time-oriented reconstruction. QEDTY's current in-memory store is intentionally simpler, but the same principle motivates keeping relationship validity indexed independently from traversal logic.

## Graph data systems

Neo4j Graph Data Science 2026.09 exposes a broad production algorithm catalog and a specialized in-memory graph catalog. Its graph creation path can consume Apache Arrow. QEDTY adopts the separation between storage/projection and analytical execution conceptually, without making Neo4j a dependency.

GraphBLAS defines standardized sparse linear-algebra building blocks for graph algorithms. This supports QEDTY's future Rust/Arrow direction: adjacency structures can eventually be projected into sparse matrices and semiring computations without changing the domain semantics.

## Benchmarks

- LDBC maintains transactional, analytical, financial and graph-analytics benchmarks.
- LDBC Graphalytics defines standard graph-analysis workloads including BFS, connected components and PageRank.
- Graph500 continues to provide large-scale BFS/SSSP benchmarks for data-intensive graph processing.

QEDTY should not claim LDBC/Graph500 performance until it has independently run their prescribed datasets, measurement rules and audit process.

## Spatial/temporal interaction

The Graph layer does not reimplement geodesy. It delegates point distance to the frozen Spatial layer and requires CRS-safe operations. Likewise, temporal activity delegates to the frozen Temporal semantics.

## Architectural implications

1. Keep ontology objects immutable and identity-stable.
2. Make adjacency and type indexes deterministic and replaceable.
3. Keep algorithm code separate from storage.
4. Keep persistence separate from query execution.
5. Make Arrow an optional bulk-data boundary rather than a hard Python dependency.
6. Preserve explicit uncertainty/provenance fields instead of collapsing them into graph weights.
7. Define golden vectors before Rust implementation.
8. Avoid claiming scale from microbenchmarks; later performance gates must use representative large graphs and independent reference implementations.

## Sources

- ISO/IEC 39075:2024 GQL: https://www.iso.org/standard/76120.html
- PGQL / SQL:2023 PGQ overview: https://pgql-lang.org/
- GraphBLAS Forum: https://graphblas.org/
- Neo4j GDS 2026.09 manual: https://neo4j.com/docs/graph-data-science/current/
- Neo4j Aion temporal-graph research overview: https://neo4j.com/research/
- LDBC benchmarks: https://ldbcouncil.org/benchmarks/
- LDBC Graphalytics: https://ldbcouncil.org/benchmarks/graphalytics/
- Graph500: https://graph500.org/
- Michail, “An Introduction to Temporal Graphs: An Algorithmic Perspective”: https://arxiv.org/abs/1503.00278
- Huang, Cheng, Wu, “Temporal Graph Traversals: Definitions, Algorithms, and Applications”: https://arxiv.org/abs/1401.1919
- Cauvi, Morawietz, Viennot, “Foremost, Fastest, Shortest: Temporal Graph Realization under Various Path Metrics”: https://arxiv.org/abs/2510.01702
- NetworkX algorithm references: https://networkx.org/documentation/stable/reference/algorithms/
