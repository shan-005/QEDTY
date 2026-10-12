# QEDTY Python–Rust differential cases

This directory holds small, deterministic JSON fixtures used by `scripts/check_python_rust_differential.py`.
They are tests, not production domain records or a replacement for `data/contracts/golden-vectors/`.

## Case format

Every document uses `schema_version: "qedty-differential-cases@1"` and a `cases` array. Each case has:

- `case_id`: immutable and unique regression identifier.
- `operation`: one of the operation IDs implemented by both adapters.
- `input`: the same JSON-compatible payload supplied to Python and Rust.
- `comparison.mode`: `exact`, `numeric`, or `vector_tolerance`.
- `comparison.absolute_tolerance` and `comparison.relative_tolerance`: required by policy for approximate output; these apply only to numeric comparisons and must be justified in the contract.
- `comparison.component_absolute_tolerances`: optional per-component absolute tolerances for mixed-unit vectors; when supplied, the vector comparator uses the matching component value instead of the global absolute tolerance.
- `expected_error`: for negative cases, the shared error category required from both implementations.
- `expected_result`: optional independent expected value used for exact outputs and reviewed numerical oracles. Approximate expected values use the same declared per-case tolerance as cross-language comparisons.

`temporal.bitemporal.contains` uses `valid_time` and `transaction_time` extents, each with required `start`/`end` keys whose values are timestamps or `null`. A missing start is unbounded toward the past, a missing end unbounded toward the future, and finite extents use `[start, end)` semantics. `temporal.timeline.query` mirrors Python's event/value `Timeline`: modes are `at_or_before`, `at_or_after`, `between`, `latest`, `ordered`, and `values`; points are ordered by normalized UTC instant then `sequence`, with insertion order retained for exact ties. Keyed `TemporalIndex` scans have a separate `temporal.index.query` contract below. `temporal.history.query` separately covers the declared `TemporalVersion` identity and `TemporalHistory` selection contract; snapshots and temporal-world-graph operations remain outside that scope.

The `graph.static.bfs` operation is deliberately narrow: `nodes` is an array of labels, `edges` an array of directed two-label arrays, and `source` the start label. Labels are trimmed; blank labels fail with `invalid_input`; edge endpoints add missing nodes; BFS visits each reachable non-source node once, with outgoing labels in lexical order. It is a static kernel, not a substitute for QEDTY’s temporal world graph.

The `graph.static.scc` operation uses the same label-only directed graph input (`nodes` and `edges`, with no source). It returns strongly connected components; labels within each component and the component list itself are lexically sorted. Labels are trimmed and must be non-blank strings, edge endpoints implicitly create nodes, repeated edges are idempotent, and malformed labels/edges fail with `invalid_input`. The empty graph returns an empty component list. This is one static kernel, not temporal-world-graph conformance.

The `graph.static.wcc` operation uses the same label-only graph input and returns weakly connected components: edge direction is ignored for connectivity, isolated declared nodes remain singleton components, and edge endpoints implicitly create vertices. Labels are trimmed and must be non-blank strings, repeated/reversed edges are idempotent for connectivity, and components and their members are lexically sorted. It is a bounded static kernel, not temporal-world-graph conformance.

The `spatial.distance.haversine` and `spatial.radius.query` operations use the named spherical mean-Earth radius of 6,371,008.8 metres, finite latitude/longitude bounds, and Haversine surface distances. The radius query trims non-blank IDs, uses last-write-wins behavior for duplicate IDs, includes distances up to `radius_m + 1e-7`, and returns IDs sorted by `(distance_m, id)`. Cell size must be in `[0.01, 180]`; invalid coordinates, radii, and cell sizes have stable error categories. This is not the Python WGS-84 ellipsoidal geodesic or full spatial-index contract.

The `spatial.distance.wgs84_geodesic` operation computes the WGS-84 ellipsoidal inverse-geodesic surface distance in metres from two latitude/longitude pairs. Python delegates to PROJ through `pyproj.Geod(ellps="WGS84")`; Rust uses the pinned GeographicLib-RS inverse algorithm. Fixed expected vectors cover one equatorial degree, the published GeographicLib reference pair, an antipodal pair, antimeridian crossing, coincident points, and invalid coordinate bounds. The deterministic generated family adds bounded random coordinate pairs with the same inputs sent to both implementations. This distance ignores height and is deliberately separate from spherical Haversine and radius-query distances.

The `temporal.index.query` operation exercises QEDTY's keyed `TemporalIndex` with string payloads. Modes are `at`, `overlapping`, `all`, `get`, `remove`, `len`, `add`, and `clear`. The `at` and `overlapping` modes preserve insertion order with half-open interval semantics; `all` sorts by start (unbounded first) then lexical key. Re-adding an identical key/extent/value is idempotent, while conflicting reuse returns `temporal_index_collision` and missing keys return `missing_key`. The string-value contract does not imply history or temporal-world-graph parity.

The `temporal.graph.snapshot` operation compares a bounded valid-time graph membership snapshot. `nodes` are non-blank string IDs; each relationship has an `id`, `source`, `target`, and nullable `valid_start`/`valid_end`. Endpoints must exist in `nodes`; finite intervals require `valid_start < valid_end`; the query instant is included at the lower bound and excluded at the upper bound. Results normalize the instant to UTC and sort unique entity and active relationship IDs lexically. This is snapshot-membership parity only, not bitemporal transaction-time selection, provenance traversal, or full temporal-world-graph history parity.

The `temporal.graph.traverse` operation adds bounded bitemporal directed reachability. It takes timezone-aware `valid_at` and `transaction_at` instants, a non-blank `source`, known node IDs, and relationships with nullable `valid_start`/`valid_end` and `transaction_start`/`transaction_end`. A relationship is traversable only when both half-open extents contain the corresponding query instant; null bounds are unbounded. The traversal is outgoing/directed, includes the source in sorted `reachable_ids`, and reports all active relationship IDs in sorted order. Duplicate IDs are idempotent only for identical records; conflicting reuse and missing endpoints are rejected. This does not claim provenance or version-lineage traversal, graph mutation history, or full temporal-world-graph parity.

The `temporal.history.query` operation compares `TemporalVersion` identity and `TemporalHistory` behavior using `create`, `all`, `get`, `add`, `as_of`, and `latest_known` modes. Canonical identifiers use the record key, valid-time extent, transaction-time extent, and value. Supersession links and metadata remain part of the stored version but do not affect the identifier preimage. History selection checks both time axes for `as_of`; `latest_known` checks transaction time only. This contract does not claim snapshot or temporal-world-graph parity.

Identity inputs follow the current hash preimage: `parts[0]` is the namespace, then remaining parts preserve their order. Quantity results compare numeric values because Python uses `Decimal` while Rust currently uses `f64`; this does **not** imply arbitrary-precision equivalence.

The `geometry.ecef.inverse` operation accepts `x_m`, `y_m`, and `z_m` in WGS-84 Earth-centred Earth-fixed coordinates and returns `[latitude_deg, longitude_deg, ellipsoidal_height_m]`. Fixed expected vectors cover the equator, both poles, a regional reference, negative height, the antimeridian, an east-quarter-turn point, and rejection of the ECEF origin with `invalid_coordinate`. The generated family builds bounded ECEF inputs from seeded geodetic coordinates and compares inverse outputs across Python and Rust; those generated round trips supplement, but do not replace, the fixed expected vectors. Component-specific absolute tolerances are `1e-8` degrees for latitude/longitude and `1e-5` metres for height; the shared vector comparator supports this unit-aware profile.

ECEF comparison tolerance is in metres for each Cartesian coordinate.

## Run

From the repository root, in a synchronized checkout:

```bash
uv run pytest -q tests/differential
uv run python scripts/check_python_rust_differential.py --generated-count 64 --seed 20261010
```

The script builds/runs the actual native JSONL adapter with `cargo run --locked`. Set `QEDTY_DIFFERENTIAL_RUST_COMMAND` only when you need an alternate runner command. If the Rust toolchain, executable, or dependencies are missing, the command fails rather than skipping native comparisons.

The generator is deterministic and has no runtime dependency on Hypothesis or Proptest. `--generated-count N` adds N cases to each of twenty-one generated families and `--seed S` records a replayable pseudo-random seed. Fixed test fixtures always run. Generated cases cover canonical JSON, identity, quantity conversion, forward WGS-84 ECEF and inverse WGS-84 ECEF, WGS-84 ellipsoidal geodesic distance, timestamp normalization, interval membership, Allen relations, static graph BFS and SCC, named spherical Haversine distance, WGS-84 ellipsoidal geodesic distance, and indexed radius query, bitemporal membership, point/event timeline queries, keyed TemporalIndex semantics, and TemporalVersion/TemporalHistory identity and query selection, plus bounded valid-time graph snapshots. The spherical spatial contract uses a mean Earth radius of 6,371,008.8 metres and does not claim equivalence with WGS-84 ellipsoidal geodesics. Extended fuzzing can be added separately after toolchain/MSRV compatibility is verified.

## Adding a confirmed regression

1. Reproduce the failure with a fixed seed and copy the smallest complete input into a checked-in case document.
2. Choose `exact` only for contract-exact data; use a numeric comparator only when the contract defines a tolerance and its units.
3. For errors, set a specific stable `expected_error` category. Do not compare only that both sides crashed.
4. Add an independently justified expected result when one can be established from a reviewed contract or external golden fixture; never copy a failing Rust output into the oracle.
5. Run the fixed-case Python test and the full native differential command. Never automatically overwrite expected outputs from the current Rust implementation.
6. Preserve failure input and relevant seed in the pull request.

## Coverage boundary

The current direct operation set is deliberately limited to semantics that have a close, reviewed Python and Rust counterpart: canonical JSON, deterministic IDs, quantity conversion, RFC 3339 normalization, checked forward/inverse WGS-84 ECEF, WGS-84 ellipsoidal inverse geodesic distance, `ContractResult` normalization, half-open interval membership, Allen interval relation classification, open-ended bitemporal membership, selected point/event timeline queries, bounded keyed TemporalIndex behavior, named spherical spatial queries, and the versioned TemporalVersion/TemporalHistory boundary under review. This does not certify arbitrary behavior of every Rust kernel or every Python domain API.

In particular, `qedty_core::graph::DirectedGraph` documents itself as a primitive for small/medium native kernels and not a replacement for QEDTY's Python temporal world-graph API. Do not claim graph-wide parity until the two sides share an explicit request/result contract and a same-input adapter. The same rule applies to spatial, propagation, uncertainty, and scenario kernels without a direct counterpart.
