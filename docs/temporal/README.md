# QEDTY Temporal 2.0.0

Temporal is the authoritative Python reference layer for time-varying QEDTY world state.

It provides:

- UTC-normalized temporal extents with explicit unbounded ends.
- Canonical `[start,end)` storage semantics compatible with PostgreSQL range design.
- Allen's 13 basic interval relations.
- Orthogonal valid-time and transaction-time coordinates for bitemporal reasoning.
- Deterministic temporal versions and historical `as_of` selection.
- Temporal granularity and calendar-aware bucketing.
- Deterministic timelines and an in-memory reference temporal index.
- Snapshot selectors and immutable snapshot metadata.
- Query helpers and overlap joins.
- JSON Schema, Protobuf, Arrow, RDF/SHACL and golden-vector boundaries.

The Python implementation is the semantic reference. Rust, Arrow, PostgreSQL/PostGIS and other backends must conform to these contracts rather than introduce competing time semantics.
