# QEDTY graph contracts

The graph layer is a directed property-graph view over the ontology and temporal semantics.
It consumes canonical entity and relationship identities; it does not redefine them.

## Semantic invariants

1. Entity and relationship identity follows the Core and Ontology identity rules.
2. Relationships are directed and typed.
3. Valid-time intervals use half-open `[valid_from, valid_to)` semantics.
4. A missing `valid_from` or `valid_to` represents an unbounded side where permitted by
   the contract.
5. Traversal at an instant applies the authoritative Temporal validity semantics.
6. Externally visible algorithm results use deterministic ordering where the operation
   contract requires it.
7. Parallel relationships are legal and remain distinct by relationship identity.
8. Content-addressed graph snapshots use the declared canonicalization and digest profile.
9. Graph algorithms do not relabel model outputs as observations; epistemic state and
   provenance remain attached to the relevant ontology objects.
10. Python is the current semantic/reference implementation. Rust implements a bounded
    native operation set; parity is limited to the operations and fixtures documented by
    the conformance matrix.

## Algorithm scope

The Python reference layer includes traversal, deterministic path operations, connectivity
measures, centrality algorithms, topological ordering, and flow analysis. Each algorithm
must document its assumptions, input constraints, numerical behavior, and output ordering.

For example, Dijkstra requires non-negative edge costs. Reliability-path scoring is a
separate multiplicative objective and must not be silently treated as additive distance.
Temporal traversal must use explicit time semantics rather than static reachability.

## Rust mapping

The Rust core provides selected in-memory graph primitives, including bounded traversal,
path, connectivity, PageRank, and max-flow operations. These are not equivalent to the
entire Python graph package or a persistent graph service.

Use the operation-level Python–Rust conformance matrix and shared fixtures to determine
exact parity. Do not describe an operation as conformant unless its exact contract and
verification evidence support that claim.

## Interoperability

JSON Schema, Protobuf, Arrow, RDF/SHACL, and future SQL/PGQ or database integrations are
representation and interoperability boundaries. They must preserve canonical graph
semantics; they do not independently define graph behavior.
