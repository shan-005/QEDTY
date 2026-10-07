# SERAPH-PCI-X Graph contract

The Graph layer is a directed property-graph view over the frozen ontology and temporal semantics.

## Semantic invariants

1. Entity and relationship identity comes from the frozen Core/Ontology identity rules.
2. Relationships are directed and typed.
3. Valid-time intervals are half-open: `[valid_from, valid_to)`.
4. `None` for `valid_from` or `valid_to` means unbounded on that side.
5. Graph traversal at an instant uses the frozen Temporal validity semantics.
6. Algorithm output is deterministically ordered by entity and relationship IDs for equal-quality solutions.
7. Parallel relationships are legal and remain distinct by relationship ID.
8. Persistence is content-addressed by the SHA-256 of canonical entity/relationship arrays.
9. Graph algorithms never relabel model outputs as observations; provenance/epistemic state remains attached to the ontology objects.
10. Arrow, Protobuf, JSON Schema, SQL/PGQ and future Rust implementations are interoperability boundaries; Python remains the semantic reference implementation in this phase.

## Algorithm policy

The initial reference implementation includes breadth/depth-first traversal, deterministic reliability paths, Dijkstra shortest paths, PageRank, closeness, betweenness, weak/strong connectivity, articulation points, topological ordering, and max-flow/min-cut analysis.

Numerical algorithms define explicit tolerances and reject invalid negative/non-finite weights where their mathematical assumptions require non-negative weights.

## Rust mapping

The future Rust workspace should implement the same `GraphPath`, snapshot, adjacency, traversal, path, connectivity, and flow semantics. The golden vectors are normative for cross-language differential testing.
